"""Experimental exact-GGUF frozen-body LoRA. Never expands a whole dense checkpoint.

Use cpu-preflight during another GPU job. gpu-smoke-and-train is for the existing
exclusive GPU queue only, after CPU results pass. Every failed attempt is terminal.
The custom derivative reconstructs each frozen weight chunk in backward rather
than retaining dequantized 27B weights in the autograd graph.
"""
import os, sys, json, argparse, hashlib, math, time, traceback, shutil
from pathlib import Path

EXPECTED_MODEL_SHA = '4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
EXPECTED_DATA_SHA = '07e6f7156883f9adb91812b2306b6dd813f60b189ae1da2610ae8c20d2d55a3c'
DISK_RESERVE = 3 * 1024**3

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024**2), b''): h.update(block)
    return h.hexdigest()

def write_json(path, obj):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)

def components():
    import numpy as np
    import torch
    from transformers.integrations.gguf.dequant import dequantize, GGML_BLOCK
    from transformers.integrations.gguf.reader import GgufHeader, load_gguf_state_dict
    class FrozenPackedMatmul(torch.autograd.Function):
        @staticmethod
        def forward(ctx,x,packed,ggml_type,out_features,chunk_rows):
            flat=x.reshape(-1,x.shape[-1]); chunks=[]
            for start in range(0,out_features,chunk_rows):
                w=dequantize(packed[start:start+chunk_rows],ggml_type,x.dtype).reshape(-1,flat.shape[-1])
                chunks.append(flat @ w.T)
            ctx.save_for_backward(packed)
            ctx.ggml_type,ctx.chunk_rows,ctx.input_shape=ggml_type,chunk_rows,x.shape
            return torch.cat(chunks,dim=-1).reshape(*x.shape[:-1],out_features)
        @staticmethod
        def backward(ctx,grad_output):
            (packed,)=ctx.saved_tensors
            go=grad_output.reshape(-1,grad_output.shape[-1])
            gx=torch.zeros((go.shape[0],ctx.input_shape[-1]),device=go.device,dtype=go.dtype)
            for start in range(0,go.shape[-1],ctx.chunk_rows):
                w=dequantize(packed[start:start+ctx.chunk_rows],ctx.ggml_type,go.dtype).reshape(-1,gx.shape[-1])
                gx.add_(go[:,start:start+w.shape[0]] @ w)
            return gx.reshape(ctx.input_shape),None,None,None,None
    class PackedLora(torch.nn.Module):
        def __init__(self,base,rank=8,alpha=16,dropout=.05):
            super().__init__();self.base_layer=base
            self.in_features,self.out_features=base.in_features,base.out_features
            self.lora_A=torch.nn.Parameter(torch.empty(rank,self.in_features,device=base.weight.device,dtype=torch.float32))
            self.lora_B=torch.nn.Parameter(torch.zeros(self.out_features,rank,device=base.weight.device,dtype=torch.float32))
            torch.nn.init.kaiming_uniform_(self.lora_A,a=math.sqrt(5));self.scaling=alpha/rank
            self.drop=torch.nn.Dropout(dropout)
        def forward(self,x):
            extra=(self.drop(x.float()) @ self.lora_A.T) @ self.lora_B.T
            return self.base_layer(x)+extra.to(x.dtype)*self.scaling
    return torch,np,dequantize,GGML_BLOCK,GgufHeader,load_gguf_state_dict,FrozenPackedMatmul,PackedLora

def cpu_preflight(model_path,out):
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':
        raise RuntimeError('cpu-preflight requires CUDA_VISIBLE_DEVICES empty before torch import')
    torch,np,dequant,block,Header,load,Frozen,Lora=components();torch.set_num_threads(1)
    head=Header.from_file(str(model_path));lazy=load(head);tests=[]
    for typ in sorted(set(t.ggml_type for t in head.tensors)):
        if typ not in block:
            tests.append({'type':typ,'kind':'unquantized_preserved','pass':typ==0});continue
        info=next(t for t in head.tensors if t.ggml_type==typ and len(t.shape)==2)
        q=lazy[info.name]; rows=3;cols=min(info.shape[-1],512)
        elems,bb=block[typ];cols=max(elems,cols//elems*elems)
        # Read only selected complete quant blocks, not the whole named tensor.
        packed=torch.from_numpy(np.copy(q.data[:rows*(cols//elems)*bb])).reshape(rows,-1)
        w=dequant(packed,typ,torch.float32).reshape(rows,cols)
        assert torch.isfinite(w).all(),f'nonfinite dequant type{typ}'
        x=torch.randn(4,cols,requires_grad=True); xr=x.detach().clone().requires_grad_()
        grad=torch.randn(4,rows)
        y=Frozen.apply(x,packed,typ,rows,2);yr=xr@w.T
        (y*grad).sum().backward();(yr*grad).sum().backward()
        forward_error=(y-yr).abs().max().item();gradient_error=(x.grad-xr.grad).abs().max().item()
        ok=torch.allclose(y,yr,rtol=2e-5,atol=2e-5) and torch.allclose(x.grad,xr.grad,rtol=2e-5,atol=2e-5)
        class Base(torch.nn.Module):
            def __init__(self):
                super().__init__();self.in_features=cols;self.out_features=rows
                self.weight=torch.nn.Parameter(packed,requires_grad=False)
            def forward(self,z):return Frozen.apply(z,self.weight,typ,rows,2)
        base=Base();m=Lora(base,rank=2,alpha=4,dropout=0)
        before=m.lora_B.detach().clone();ph=hashlib.sha256(base.weight.numpy().tobytes()).hexdigest()
        opt=torch.optim.SGD([m.lora_A,m.lora_B],lr=.01)
        target=torch.randn(4,rows)
        for _ in range(2):
            opt.zero_grad();loss=(m(x.detach())-target).square().mean();loss.backward();opt.step()
        changed=not torch.equal(before,m.lora_B);frozen=ph==hashlib.sha256(base.weight.numpy().tobytes()).hexdigest()
        tests.append({'type':typ,'sample_tensor':info.name,'rows':rows,'cols':cols,'forward_max_abs_error':forward_error,'input_gradient_max_abs_error':gradient_error,'adapter_changed':changed,'base_unchanged':frozen,'finite_loss':math.isfinite(loss.item()),'pass':bool(ok and changed and frozen and math.isfinite(loss.item()))})
    from transformers import AutoConfig, AutoTokenizer
    config=AutoConfig.from_pretrained(str(model_path.parent),gguf_file=model_path.name,local_files_only=True)
    tok=AutoTokenizer.from_pretrained(str(model_path.parent),gguf_file=model_path.name,local_files_only=True)
    text=tok.apply_chat_template([{'role':'user','content':'여행 일정의 시간을 바꿔 주세요.'}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    result={'status':'passed' if all(t['pass'] for t in tests) else 'failed','model_sha256':sha256(model_path),'architecture':head.architecture,'tests':tests,'passed':sum(t['pass'] for t in tests),'total':len(tests),'config_model_type':config.model_type,'tokenizer_size':len(tok),'chat_template_sha256':hashlib.sha256(tok.chat_template.encode()).hexdigest(),'sample_template_tokens':len(tok.encode(text)),'gpu_loaded':False,'full_model_trained':False,'derivative_scope':'real GGUF block CPU float32 input gradients and two LoRA updates; not full-model/CUDA/accuracy'}
    assert result['model_sha256']==EXPECTED_MODEL_SHA
    write_json(out/'cpu_preflight.json',result)
    if result['status']!='passed':raise RuntimeError('mixed GGUF CPU derivative tests failed')

def patch_packed_loader(Frozen,torch,dequant,block):
    from transformers.integrations.gguf import utils,kernels
    from transformers.quantizers import quantizer_gguf
    class TorchPackedKernel:
        def supports(self,typ):return typ in block
        def dequantize(self,w,typ,rows,cols,dtype):return dequant(w,typ,dtype).reshape(rows,cols)
        def get_rows(self,w,indices,typ,cols,dtype):return dequant(w.index_select(0,indices),typ,dtype).reshape(-1,cols)
    kernel=TorchPackedKernel()
    quantizer_gguf.get_gguf_kernel=lambda:kernel
    kernels._gguf_kernel=kernel
    def forward(module,x):
        if module.input_permutation is not None:x=x.index_select(-1,module.input_permutation)
        out=Frozen.apply(x,module.weight,module.ggml_type,module.out_features,128)
        return out if module.bias is None else out+module.bias
    utils.GgufLinear.forward=forward
    def after(quantizer,model,**kwargs):
        for name,module in quantizer.packed_modules.items():
            if name in quantizer.input_permutations:module.input_permutation=quantizer.input_permutations[name].to(module.weight.device)
        # This experiment uses ordinary differentiable model layers, never inference-only Hub kernels.
        model._weight_conversions=None
        return model
    quantizer_gguf.GgufHfQuantizer._process_model_after_weight_loading=after
    return utils

def encode_rows(tok, data):
    rows=[json.loads(l) for l in data.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
    if len(rows)!=2613:raise RuntimeError('expected all 2613 training rows')
    encoded=[]
    for i,row in enumerate(rows):
        msgs=row.get('messages') or [{'role':'user','content':row['prompt']},{'role':'assistant','content':row['completion']}]
        if msgs[-1].get('role')!='assistant':raise RuntimeError('last completion must be assistant')
        prompt=tok.encode(tok.apply_chat_template(msgs[:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False),add_special_tokens=False)
        complete=tok.encode(tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=False,enable_thinking=False),add_special_tokens=False)
        if complete[:len(prompt)]!=prompt:raise RuntimeError(f'chat completion prefix not identical at row {i}')
        if len(complete)>4096:raise RuntimeError(f'overlength row {i}: no silent itinerary truncation')
        encoded.append((complete,[-100]*len(prompt)+complete[len(prompt):]))
    return encoded

def gpu_smoke_and_train(args,out):
    if not args.execute_in_queue:raise RuntimeError('GPU mode requires exclusive existing queue dispatch')
    cpu=json.loads(Path(args.cpu_report).read_text())
    if cpu['status']!='passed' or cpu['model_sha256']!=EXPECTED_MODEL_SHA:raise RuntimeError('CPU prerequisite not passed')
    import subprocess
    active=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True).stdout.strip()
    if active:raise RuntimeError('another GPU process is present; no competing model load')
    if shutil.disk_usage(out).free<DISK_RESERVE+260*1024**2:raise RuntimeError('disk reserve plus 260MiB adapter/log budget not available')
    if sha256(args.model)!=EXPECTED_MODEL_SHA or sha256(args.data)!=EXPECTED_DATA_SHA:raise RuntimeError('fixed model/data identity mismatch')
    torch,np,dequant,block,Header,load,Frozen,Lora=components();torch.set_num_threads(2)
    utils=patch_packed_loader(Frozen,torch,dequant,block)
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from transformers import GgufConfig
    torch.manual_seed(20261019)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tok=AutoTokenizer.from_pretrained(str(args.model.parent),gguf_file=args.model.name,local_files_only=True)
    encoded=encode_rows(tok,args.data)
    # The exclusive slot validates CUDA arithmetic before loading the 27B model.
    header=Header.from_file(str(args.model));lazy=load(header);cuda_tests=[]
    for typ in sorted(set(t.ggml_type for t in header.tensors)):
        if typ not in block:continue
        info=next(t for t in header.tensors if t.ggml_type==typ and len(t.shape)==2)
        elems,bb=block[typ];cols=512//elems*elems;rows=3
        packed=torch.from_numpy(np.copy(lazy[info.name].data[:rows*(cols//elems)*bb])).reshape(rows,-1).cuda()
        x=torch.randn(4,cols,device='cuda',dtype=dtype,requires_grad=True)
        xr=x.detach().clone().requires_grad_();g=torch.randn(4,rows,device='cuda',dtype=dtype)
        w=dequant(packed,typ,dtype).reshape(rows,cols)
        y=Frozen.apply(x,packed,typ,rows,128);yr=xr@w.T
        (y*g).sum().backward();(yr*g).sum().backward()
        passed=bool(torch.allclose(y,yr,rtol=.03,atol=.03) and torch.allclose(x.grad,xr.grad,rtol=.03,atol=.03))
        cuda_tests.append({'type':typ,'pass':passed})
        if not passed:raise RuntimeError(f'CUDA packed derivative failed type {typ}')
    write_json(out/'cuda_blocks.json',{'tests':cuda_tests,'passed':sum(x['pass'] for x in cuda_tests),'total':len(cuda_tests),'dtype':str(dtype)})
    del packed,x,xr,g,w,y,yr,lazy;torch.cuda.empty_cache()
    # Enforce headroom after other queued jobs and any retained tmpfs model cache.
    cg=Path('/sys/fs/cgroup');limit=int((cg/'memory.max').read_text());current=int((cg/'memory.current').read_text())
    if limit-current < 12*1024**3:raise RuntimeError('less than 12GiB cgroup RAM headroom before full model load')
    model=AutoModelForCausalLM.from_pretrained(str(args.model.parent),gguf_file=args.model.name,local_files_only=True,quantization_config=GgufConfig(dequantize=False),dtype=dtype,device_map={'':'cuda:0'},attn_implementation='eager')
    # Freeze every original parameter. Train only explicit language linear adapters.
    for p in model.parameters():p.requires_grad_(False)
    targets=[]
    for name,module in list(model.named_modules()):
        if isinstance(module,utils.GgufLinear) and name.startswith('model.layers.'):
            model.set_submodule(name,Lora(module));targets.append(name)
    if not targets:raise RuntimeError('no language packed linear targets found')
    if any(p.is_meta for p in model.parameters()):raise RuntimeError('unmaterialized model parameter')
    trainable=[p for p in model.parameters() if p.requires_grad]
    model.config.use_cache=False;model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.train()
    write_json(out/'token_audit.json',{'rows':len(encoded),'max_tokens':max(len(x[0]) for x in encoded),'targets':targets,'trainable_parameters':sum(p.numel() for p in trainable),'data_sha256':EXPECTED_DATA_SHA,'packed_original_sha256':EXPECTED_MODEL_SHA,'base_representation':'exact original mixed IQ GGUF; no NF4 requantization'})
    opt=torch.optim.AdamW(trainable,lr=2e-5)
    initial=[p.detach().clone() for p in trainable]
    log=(out/'train_log.jsonl').open('x',encoding='utf-8')
    def step(examples,scale=1):
        total=0.
        for ids,labels in examples:
            if shutil.disk_usage(out).free<DISK_RESERVE:raise RuntimeError('disk reserve reached')
            inp=torch.tensor([ids],device='cuda');lab=torch.tensor([labels],device='cuda')
            loss=model(input_ids=inp,labels=lab,use_cache=False).loss
            if not torch.isfinite(loss):raise RuntimeError('nonfinite loss')
            (loss/scale).backward();total+=loss.detach().item()
        if not all(p.grad is None or torch.isfinite(p.grad).all() for p in trainable):raise RuntimeError('nonfinite gradients')
        torch.nn.utils.clip_grad_norm_(trainable,1.0);opt.step();opt.zero_grad(set_to_none=True)
        if torch.cuda.mem_get_info()[0]<1024**3:raise RuntimeError('VRAM reserve under1GiB after update')
        return total/len(examples)
    # Progressive real rows, no shortening: stages choose bounded rows, full audit includes every row.
    smoke=[]
    for cap in (2048,4096):
        eligible=sorted((r for r in encoded if len(r[0])<=cap),key=lambda r:len(r[0]),reverse=True)
        if len(eligible)<2:raise RuntimeError(f'not enough intact rows for{cap}token smoke')
        for update in range(2):
            started=time.monotonic();loss=step(eligible[update:update+1],1)
            smoke.append({'cap':cap,'update':update,'rows':1,'seconds':time.monotonic()-started,'loss':loss,'peak_allocated':torch.cuda.max_memory_allocated(),'peak_reserved':torch.cuda.max_memory_reserved()})
    changed=any(not torch.equal(a,p) for a,p in zip(initial,trainable));del initial
    if not changed:raise RuntimeError('adapter unchanged after smoke')
    write_json(out/'smoke.json',{'status':'passed','stages':smoke,'adapter_changed':changed,'base_frozen':all(not p.requires_grad for n,p in model.named_parameters() if 'lora_' not in n),'original_quantizer_trainable_claim':False,'custom_derivative_cpu_and_cuda_verified':True})
    # Smoke updates are discarded; baseline starts from seeded initial LoRA weights.
    torch.manual_seed(20261019)
    for name in targets:
        m=model.get_submodule(name);torch.nn.init.kaiming_uniform_(m.lora_A,a=math.sqrt(5));torch.nn.init.zeros_(m.lora_B)
    opt=torch.optim.AdamW(trainable,lr=2e-5);total=math.ceil(len(encoded)/16)
    rng=torch.Generator().manual_seed(20261019);order=torch.randperm(len(encoded),generator=rng).tolist()
    for update in range(total):
        if update<max(1,int(.05*total)):lr=2e-5*(update+1)/max(1,int(.05*total))
        else:lr=2e-5*.5*(1+math.cos(math.pi*(update-int(.05*total))/max(1,total-int(.05*total))))
        for g in opt.param_groups:g['lr']=lr
        subset=[encoded[i] for i in order[update*16:(update+1)*16]]
        loss=step(subset,len(subset));event={'update':update+1,'total_updates':total,'rows_seen':min((update+1)*16,len(encoded)),'loss':loss,'lr':lr,'peak_allocated':torch.cuda.max_memory_allocated()}
        log.write(json.dumps(event)+'\n');log.flush()
        write_json(out/'progress.json',event)
    log.close()
    adapter={n:p.detach().cpu() for n,p in model.named_parameters() if p.requires_grad}
    from safetensors.torch import save_file
    save_file(adapter,str(out/'adapter.safetensors'))
    if shutil.disk_usage(out).free<DISK_RESERVE:raise RuntimeError('saved adapter leaves less than 3GiB disk reserve')
    write_json(out/'adapter_config.json',{'rank':8,'alpha':16,'dropout':.05,'targets':targets,'seed':20261019,'base_sha256':EXPECTED_MODEL_SHA,'data_sha256':EXPECTED_DATA_SHA,'format':'custom packed GGUF LoRA A/B, unmerged; explicit conversion required for llama.cpp','our_finetuning':True})
    write_json(out/'completed.json',{'status':'completed','rows':2613,'updates':total,'adapter_sha256':sha256(out/'adapter.safetensors'),'base_sha256':EXPECTED_MODEL_SHA,'evaluation_pending':True,'product_adoption':False})

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['cpu-preflight','gpu-smoke-and-train'],required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--data',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--cpu-report');p.add_argument('--execute-in-queue',action='store_true');args=p.parse_args()
    if args.mode=='cpu-preflight':os.environ['CUDA_VISIBLE_DEVICES']=''
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    if (out/'failed.json').exists() or (out/'completed.json').exists():raise RuntimeError('terminal attempt exists; do not rerun')
    try:
        write_json(out/'started.json',{'mode':args.mode,'pid':os.getpid(),'unix_time':time.time()})
        if args.mode=='cpu-preflight':cpu_preflight(args.model,out)
        else:gpu_smoke_and_train(args,out)
    except BaseException as exc:
        write_json(out/'failed.json',{'status':'failed','mode':args.mode,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'unix_time':time.time(),'retry_requires_fix':True})
        raise
if __name__=='__main__':main()
