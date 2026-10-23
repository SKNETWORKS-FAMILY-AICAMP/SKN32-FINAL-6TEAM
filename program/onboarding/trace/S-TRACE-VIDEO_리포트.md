# S-TRACE-VIDEO 완료 리포트

## 결과

A-COP에 들어온 취소 및 환불 문의 한 건이 답변과 기록으로 남을 때까지를 251.1초 영상으로 만들었다.
도입과 마무리는 각각 10초다. 기존 정지 그림 17장은 수정하거나 삭제하지 않았다.

## 만든 파일

- `program/onboarding/trace/취소환불_케이스_추적_유튜브.mp4`
- `program/onboarding/trace/취소환불_케이스_추적_자막.srt`
- `program/onboarding/trace/취소환불_케이스_추적_내레이션.txt`
- `program/onboarding/trace/취소환불_케이스_추적_챕터.txt`
- `program/onboarding/trace/취소환불_케이스_추적_썸네일.png`
- `program/onboarding/trace/S-TRACE-VIDEO_리포트.md`

## 재생성

```powershell
python program/onboarding/trace/make_trace_video_youtube.py
```

이 명령 하나가 영상용 스틸을 임시 생성하고 영상, 자막, 대본, 챕터, 썸네일, 리포트를 다시 만든다.
중간 산출물을 손으로 만들 필요가 없다.

## 읽기 시간 계산

장면별 체류 시간을 고정 초 목록으로 적지 않았다.
한국어 자막의 공백 제외 글자 수와 초당 7.2자 기준으로 각 자막 시간을 계산하고, 장면별 최소 시간과 비교해 더 긴 값을 사용했다.
계산 뒤 모든 경계를 30fps 프레임에 맞췄다.

## 필수 항목 확인

- 화면 내부 움직임: 각 단계에서 왼쪽 문서와 오른쪽 문서 사이를 데이터 입자가 이동한다.
- 줄의 순차 등장: 오른쪽 전달 문서의 내용을 여덟 구간으로 나누어 순서대로 공개한다.
- 진행바: 각 단계가 시작될 때 해당 칸이 약 0.9초 동안 채워진다.
- 시선 유도: 입력, 변환, 출력, 결론 순서로 확대 이동하고 설명하지 않는 영역을 어둡게 처리한다.
- 한국어 자막: 영상에 태워 넣었고 같은 시간축의 SRT 파일을 만들었다.
- 도입과 마무리: 각각 10초다.
- 규격: 1920x1080, 30fps, H.264, yuv420p, faststart다.
- 길이: 251.1초로 3분에서 6분 사이에 있다.

## 기술 검증

`ffprobe`로 코덱, 해상도, 프레임률, 픽셀 형식, 길이, 크기를 확인했다.
`ffmpeg`로 영상과 오디오 스트림 전체를 다시 디코딩해 재생 오류도 확인했다.

```text
codec_name=h264
width=1920
height=1080
r_frame_rate=30/1
pix_fmt=yuv420p
audio_codec=aac
sample_rate=48000
channels=1
duration=251.133333
size=62486796 bytes, 59.6 MiB
faststart=true
decode_check=true
```

실행 환경은 다음과 같다.

```text
ffmpeg version 9.0.1-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers
ffprobe version 9.0.1-full_build-www.gyan.dev Copyright (c) 2007-2026 the FFmpeg developers
```

## 내용 정확성

- 단계 12개와 상태 12개를 별도 축으로 설명했다.
- 1번 신원 확인과 2번 중복 확인에는 Case 상태가 없다고 명시했다.
- Team은 실행하지 않고 판단과 제안만 돌려준다고 명시했다.
- 실행은 승인 경로에서 한다고 설명했지만 원문에 없는 구체 실행 결과나 코드 경로는 추가하지 않았다.
- 9번 검토 단계는 `response_review.enabled = false`로 표시했다.
- 취소라는 표현이 들어왔지만 intent는 return이라는 장면을 독립 자막으로 강조했다.
- 본 경로는 전부 통과한 길이며 마지막에 아홉 갈래를 보여 준다.
- 확인되지 않은 숫자, 필드, 코드 경로는 새로 만들지 않았다.

## 음향과 저작권

음성 합성은 쓰지 않았다.
외부 음악과 외부 샘플도 쓰지 않았다.
배경음은 생성기 안에서 사인파만으로 합성한 무보컬 패드다.
제3자 음원 데이터가 포함되지 않는다.
사람 내레이션은 별도 대본에 맞춰 나중에 녹음할 수 있다.

## 보존과 제외 사항

- 기존 PNG 수: 17장
- 생성 전후 SHA-256 일치: true
- 기존 PNG를 영상에 바로 굽지 않고 원본 Python 데이터에서 임시 스틸을 다시 그렸다.
- 원본에 있던 금지 기호는 영상용 임시 스틸에서 등호와 일반 문장으로 바꾸었다.
- 최신 지시에 따라 모든 새 파일을 `program/onboarding/trace/` 아래에만 만들었다.
- 외부 BGM은 넣지 않았다. 대신 외부 샘플이 없는 합성 배경음을 넣었다.
