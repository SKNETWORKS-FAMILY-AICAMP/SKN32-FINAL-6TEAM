import { ButtonLink } from "@/components/ui";
import { routes } from "@/lib/routes";
import styles from "./page.module.css";

export default function LandingPage() {
  return <section className={styles.landing}><div><p className={styles.eyebrow}>YOUR PLAN, OUR CARE</p><h1>여행 계획은 한곳에서,<br />여정은 계속 이어지도록.</h1><p className={styles.description}>새로운 여행 계획을 등록하거나,<br />준비된 여행의 일정과 대화를 이어서 확인하세요.</p><ButtonLink variant="primary" href={routes.newTrip}>+ 첫 여행 등록하기</ButtonLink></div></section>;
}
