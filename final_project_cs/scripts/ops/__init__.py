"""운영(상시 실행) 도구 — 등록·실행·점검.

    python -m scripts.ops.install_services      무엇을 걸지 **보여만 준다**(기본)
    python -m scripts.ops.tick <작업> --show    스케줄러가 부를 명령을 보여만 준다
    python -m scripts.ops.healthcheck           상시 실행이 살아 있나

★이 폴더의 어떤 것도 **기본값으로는 기계를 바꾸지 않는다.** 등록은 `--apply` 를
  줘야 하고, 그때도 무엇이 바뀌는지 먼저 찍는다. 문서는
  `wiki/operations/always-on.md` 와 `wiki/operations/move-to-server.md` 다.
"""
