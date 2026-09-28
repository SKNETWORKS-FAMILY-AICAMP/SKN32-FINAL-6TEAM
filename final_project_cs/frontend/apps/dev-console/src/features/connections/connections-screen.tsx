"use client";

import { useState } from "react";
import { ArrowRight, Monitor, Server, Boxes } from "lucide-react";
import { Badge, Button, Notice, PageHeading, Panel } from "@/components/ui";
import { dataMode } from "@/lib/gateway";
import styles from "./connections.module.css";

export function ConnectionsScreen() {
  const [environment, setEnvironment] = useState<"local" | "shared">("local");
  const local = environment === "local";
  return <><PageHeading eyebrow="개발 작업공간 / 연결 안내" title="개발팀과 연결하는 방법" description="화면, 코어의 테스트 API, 에이전트팀을 순서대로 연결합니다." action={<Badge tone="warning">실제 API 미연결</Badge>} />
    <Notice>{dataMode === "demo" ? "현재는 브라우저의 샘플 데이터 어댑터로 동작합니다. 아래 선택은 연결 방식 안내이며 실제 서버 설정을 변경하지 않습니다." : "데이터 모드가 설정되지 않았습니다. .env.local에서 NEXT_PUBLIC_CONSOLE_DATA_MODE=demo를 지정하고 서버를 다시 실행하면 샘플을 사용할 수 있습니다."}</Notice>
    <div className={styles.switcher} aria-label="개발 환경 설명 선택"><Button onClick={() => setEnvironment("local")} aria-pressed={local} variant={local ? "primary" : "secondary"}>내 PC에서 개발</Button><Button onClick={() => setEnvironment("shared")} aria-pressed={!local} variant={!local ? "primary" : "secondary"}>공용 개발 서버</Button></div>
    <div className={styles.flow}><Panel title="01 콘솔" aside={<Monitor size={18} aria-hidden="true" />}><p>{local ? "개발자 PC에서 화면을 실행합니다." : "공용 개발 콘솔 URL로 접속합니다."}</p><p className={styles.muted}>테스트 입력 · 실행 요청 · 기록 표시</p><Badge tone="success">프론트엔드 구현</Badge></Panel><ArrowRight className={styles.arrow} aria-hidden="true" /><Panel title="02 코어 API" aside={<Server size={18} aria-hidden="true" />}><p>{local ? "내 PC의 코어가 개발 중인 코드를 호출합니다." : "공용 코어가 서버에 연결된 팀 버전을 호출합니다."}</p><p className={styles.muted}>작업 생성 · 실행 ID · 기록 저장·조회</p><Badge tone="warning">테스트 API 연결 필요</Badge></Panel><ArrowRight className={styles.arrow} aria-hidden="true" /><Panel title="03 에이전트팀" aside={<Boxes size={18} aria-hidden="true" />}><p>액티비티 · 요식업 · 이동</p><p className={styles.muted}>입력 · 도구 응답 · 비교값 · 최종 결과 기록</p><Badge tone="warning">공통 기록 규격 연결 필요</Badge></Panel></div>
    <div className={styles.details}><Panel title="개발자가 실행하는 순서"><ol><li>{local ? "수정 중인 팀 코드가 포함된 코어를 실행합니다." : "테스트할 팀 버전을 공용 개발 코어에 반영합니다."}</li><li>콘솔과 코어의 테스트 API를 연결합니다.</li><li>팀을 선택하고 테스트를 실행합니다.</li><li>같은 실행 ID에 연결된 조회값과 결과를 확인합니다.</li></ol><p className={styles.muted}>각 팀은 코어 내부 모듈 또는 별도 서비스로 연결할 수 있습니다.</p></Panel><Panel title="연동 전에 합의할 계약"><ul><li>팀 호출 입력과 버전 선택</li><li>실행·단계 ID, 병렬 작업과 실패 상태</li><li>조회값·비교 기준·근거 참조</li><li>테스트 사례와 같은 입력의 A/B 실행</li></ul><p className={styles.muted}>프로젝트의 <code>API_CONTRACT.md</code>에 프론트 표시 계약과 담당별 연결 항목을 정리했습니다.</p></Panel></div>
  </>;
}
