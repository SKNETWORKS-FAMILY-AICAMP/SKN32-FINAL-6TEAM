import { ButtonLink } from "@/components/ui";
import styles from "./page.module.css";

export default function NotFound() {
  return <section className={styles.landing}><div><h1>페이지를 찾을 수 없어요</h1><p className={styles.description}>여행 링크를 확인하거나 새로운 계획을 등록해 주세요.</p><ButtonLink href="/" variant="primary">메인 홈페이지로</ButtonLink></div></section>;
}
