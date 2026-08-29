from tokenizers import Tokenizer
from transformers import PreTrainedTokenizerFast

raw = Tokenizer.from_file(r'E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\blobs\443909a61d429dff23010e5bddd28ff530edda00')
print("raw tokenizer loaded")
tok = PreTrainedTokenizerFast(tokenizer_object=raw)
print("wrapped ok", tok.vocab_size)
