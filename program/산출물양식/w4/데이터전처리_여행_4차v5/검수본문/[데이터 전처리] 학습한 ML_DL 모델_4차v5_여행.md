# [데이터 전처리] 학습한 ML_DL 모델_4차v5_여행

[그림]

| SK 네트웍스 Family AI 32기: 6팀 / 학습한 ML / DL 모델 |


| 산출물 단계 | 데이터 전처리 |
|---|---|
| 제출 일자 | 2026. 9. 28. |
| 깃허브 경로 | https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM |
| 작성 팀원 | 김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우 |


| 학습한 ML / DL 모델 (Trained ML / DL Model) |

모델 개요
모델 유형 : kakaobank/kf-deberta-base를 파인튜닝한 문장 분류기 2종(요청 종류, 문제 코드)
담당 태스크 : 여행 고객 메시지의 요청 종류 5종과 문제 코드 17종 분류
프레임워크 / 버전 : PyTorch 2.13.0, Transformers 5.16.1, scikit-learn 1.9.1
제품 연결: 아직 연결하지 않았다. 제품의 메시지 분류는 Gemma 4 12B(Ollama, 없으면 OpenAI)가 한다. 제출 모델은 호출 규격 검사까지 마쳤고, 제품 분류 체계(18종)에 맞춰 다시 학습한 뒤 연결을 검토한다
모델 파일·로딩: intent/ · issue_code/ 폴더(SafeTensors 가중치·토크나이저·metrics.json)를 Transformers로 불러 쓴다. CPU 추론 지연은 아직 재지 않았다
성능: 시험 조각에서 기준 모델 라벨과의 일치율 요청 종류 0.8311, 문제 코드 0.8017(사람 정답 아님)
다른 팀 모델: 이동의 판정 학습 모델(HistGradientBoosting 2종)은 미채택 비교 모델, 요식의 대체 유사도 모델(e5-small 미세조정)은 시험 모델이며 제출 대상이 아니다. 액티비티는 학습 모델이 없다(해당 없음)
모델 구조 정의
2.1 구성 요소 (전처리 · 학습 · 후처리)

| 구성 요소 | 유형 | 기능 | 의존성 | 비고 |
|---|---|---|---|---|
| 전처리 | 정규화·마스킹 | NFKC 정규화, 반복 글자 축약, 개인정보 치환 | 제품 마스킹 규칙 | 학습·추론 공용 |
| 특징 | 토크나이저 | 하위 단어 분할, 최대 96토큰 | transformers | 모델 폴더에 함께 저장 |
| 학습기 1 | kf-deberta-base(FT) | 요청 종류 5분류 | transformers, torch | 학습 4,859건 + 합성 문장 474건 |
| 학습기 2 | kf-deberta-base(FT) | 문제 코드 17분류 | transformers, torch | 학습 4,867건 + 합성 문장 474건 |
| 후처리 | softmax · 최대값 | 확률이 가장 큰 라벨과 그 확률 반환 | torch | 라벨 밖 결과는 분류 실패로 처리 |

비교·시험 모델(제출 대상 아님)

| 구성 요소 | 유형 | 기능 | 의존성 | 비고 |
|---|---|---|---|---|
| 이동 판정 | HistGradientBoosting v1 · v2 | 판정 3분류(성립·불가·근거 부족) | scikit-learn | 미채택, pkl 2.9 · 1.6MB |
| 요식 유사도 | e5-small(FT) | 문장 임베딩, 이웃 상위 3곳 | transformers, torch | 시험 모델, 학습 770곳 |

2.2 입 · 출력 스펙

| 입·출력 필드 | 타입 | shape / 길이 | 설명 |
|---|---|---|---|
| text | str | 메시지 1건 | 마스킹한 고객 메시지 |
| input_ids | int64 | [1, 최대 96] | 토크나이저 출력 |
| logits | float32 | [1, 라벨 수] | 변환 전 점수. 라벨 수는 요청 종류 5, 문제 코드 17 |
| probability | float32 | [1, 라벨 수] | logits에 softmax를 적용한 값(합 1) |
| label, confidence | str, float | 1개, 0~1 | 확률이 가장 큰 라벨과 그 확률 |

요청 종류 라벨: itinerary_submit(일정 제출), incident_report(사건 신고), confirm_request(확인 요청), adjust_reject(조정 거부), other(그 외). 문제 코드 17종은 activity·booking·dining·flight·lodging·mobility 영역별 코드와 other다.

| 입·출력 필드 | 타입 | shape / 길이 | 설명 |
|---|---|---|---|
| features(이동) | float | [1, 27], v2는 [1, 33] | 구간·시각·자료 유무 등 판정 입력 특징 |
| label(이동) | str | 1개 | 성립·불가·근거 부족 |
| embedding(요식) | float32 | [1, 384] | 가게 설명 한 문장의 정규화한 벡터 |

2.3 학습 데이터 · 의존 라이브러리 다이어그램
[그림]
그림 1. 학습 데이터, 라이브러리, 산출 파일의 관계(위 줄 코어 제출 모델, 아래 줄 이동 비교 모델)
학습 환경은 PyTorch 2.13.0+cu130(CUDA 13.0), Transformers 5.16.1, scikit-learn 1.9.1이다. CPU 추론 확인 환경은 PyTorch 2.12.0+cpu, Transformers 5.13.0, scikit-learn 1.5.2이다.
모델 저장 및 추론
3.1 저장 · 로딩 파이프라인
모델 파일 : intent/ · issue_code/ (각 폴더에 model.safetensors, config.json, tokenizer.json, tokenizer_config.json, metrics.json), SHA256SUMS.txt

| 항목 | 값 | 단위 | 측정 조건 | 서비스 타겟 | 비고 |
|---|---|---|---|---|---|
| 크기(요청 종류) | 709 | MiB | model.safetensors | 미정 | 토크나이저 파일 별도 |
| 크기(문제 코드) | 709 | MiB | model.safetensors | 미정 | 토크나이저 파일 별도 |
| CPU 추론 지연 | 미측정 | ms | 해당 없음 | 미정 | 제품 연결 전 측정 예정 |
| 파일 무결성 | 10/10 | 파일 | SHA256SUMS.txt 대조 | 전부 일치 | 2026-09-28 |

로딩: 모델 폴더를 Transformers의 AutoTokenizer·AutoModelForSequenceClassification으로 불러 최대 96토큰으로 자르고, logits에 softmax를 적용해 가장 큰 라벨을 고른다. 제품 코드에서는 LocalLabelModel(model_dir).predict(text)로 같은 과정을 부른다.
3.2 성능 · 한계와 후속 연계

| 구분 | 항목 | 값 / 방법 | 설명 및 관리 방안 |
|---|---|---|---|
| 저장 | 포맷 | SafeTensors | 안전 로딩, 모델 폴더별 metrics.json에 학습 설정·지표 보관 |
| 성능 | 요청 종류 | 일치율 0.8311, 95% 신뢰구간 [0.8013, 0.8593], F1 0.4368 | 시험 604건, 기준 모델 라벨 기준. 선정은 검증 점수(0.8659)로 |
| 성능 | 문제 코드 | 일치율 0.8017, 95% 신뢰구간 [0.7683, 0.8350], F1 0.5904 | 시험 600건, 기준 모델 라벨 기준. 선정은 검증 점수(0.7917)로 |
| 한계 | 라벨 기준 | 사람이 단 정답 0건 | 기준 모델 라벨의 오류가 그대로 학습된다. 사람 정답 평가 데이터를 만든다 |
| 한계 | 라벨 체계 | 제출 17종, 제품 18종 | 「이미 바꾼 예약 되돌리기 요청」을 낼 수 없다. 18종으로 다시 학습한다 |
| 한계 | 심각도·감정 | 학습 데이터 없음 | 제품은 LLM 값을 쓴다 |
| 연계 | 제품 연결 | 미연결 | 재학습·CPU 지연 측정 뒤 LLM 분류와 비교해 연결 여부를 정한다 |
| 연계 | 팀 라우팅 | 문제 코드와 요청 종류 | 문제 코드 앞부분(activity·dining·mobility 등 영역)과 요청 종류 두 가지로 담당 팀을 정한다. 지금은 제품 LLM의 분류값을 쓴다 |

변경 이력 및 적용 전략

| 변경일 | 변경자 | 변경내용 | 영향 받는 항목 | 비고 |
|---|---|---|---|---|
| 2026.09.17 | A-COPilot | 선정 모델의 구조·저장·추론 작성 | 전체 | v1.0 |
| 2026.09.28 | A-COPilot | 제품 미연결 상태와 라벨 체계 차이 명시, 파일 무결성 확인, 범위를 여행 과제로 한정(이전 판의 쇼핑 리뷰 감정 모델 제외) | 전체 | v2.0 |

적용 전략: 모델을 다시 학습하면 새 폴더에 저장하고 기존 폴더를 덮어쓰지 않는다. 받는 쪽은 SHA256SUMS.txt로 파일을 확인한 뒤 교체한다. 제출 위치: https://drive.google.com/drive/folders/1nMDeAqeSsLqeNoJg_N_8xf5s8wyC06ly
