"""이미 보관된 ARM 임베딩 모델을 제한된 자원으로 연다."""
import os

os.execv(os.environ["LLAMA_BIN"], [os.environ["LLAMA_BIN"], "-m", os.environ["EMBED_FILE"],
         "--embedding", "--pooling", "cls", "-ngl", "0", "-t", "2", "-c", "8192",
         "-b", "512", "-ub", "512", "-np", "1", "--host", "127.0.0.1", "--port", "18313"])
