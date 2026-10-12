"""GPU를 사용하지 않고 GGUF 구조·텐서 모양만 읽는다."""
import struct

def read_header(path):
    with open(path, 'rb') as f:
        def number(fmt):
            size = struct.calcsize('<'+fmt)
            return struct.unpack('<'+fmt, f.read(size))[0]
        def string():
            return f.read(number('Q')).decode('utf-8')
        def value(kind, keep=True):
            types={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in types:
                result=number(types[kind]);return result if keep else None
            if kind==8:
                length=number('Q')
                if keep:return f.read(length).decode('utf-8')
                f.seek(length,1);return None
            if kind==9:
                subtype=number('I');count=number('Q')
                if not keep and subtype in types:
                    f.seek(count*struct.calcsize('<'+types[subtype]),1);return None
                result=[] if keep else None
                for _ in range(count):
                    x=value(subtype,keep)
                    if keep:result.append(x)
                return result
            raise ValueError('Unknown GGUF metadata type '+str(kind))
        assert f.read(4)==b'GGUF'
        version=number('I');assert version in [2,3]
        tensor_count=number('Q');field_count=number('Q');fields={}
        for _ in range(field_count):
            key=string();kind=number('I')
            keep=not key.startswith('tokenizer.') and kind!=9
            result=value(kind,keep)
            if keep:fields[key]=result
        tensors={}
        for _ in range(tensor_count):
            name=string();dimensions=[number('Q') for _ in range(number('I'))]
            kind=number('I');offset=number('Q')
            assert name not in tensors
            tensors[name]={'dimensions':dimensions,'type':kind}
        return {'version':version,'fields':fields,'tensors':tensors,'tensor_count':tensor_count}
