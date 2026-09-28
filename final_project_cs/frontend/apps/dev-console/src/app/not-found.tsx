import { ButtonLink, Notice, PageHeading } from "@/components/ui";
export default function NotFound() { return <><PageHeading title="화면을 찾을 수 없어요" /><Notice>주소를 확인하거나 팀별 테스트에서 다시 시작해 주세요.</Notice><p style={{ marginTop: 16 }}><ButtonLink href="/teams">팀별 테스트로 이동</ButtonLink></p></>; }
