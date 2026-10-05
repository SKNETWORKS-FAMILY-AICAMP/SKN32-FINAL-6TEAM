import type { ConsentCode } from "./consent-model";

/**
 * `[2026-10-05 사용자 지시]` 약관 전문의 정본(웹에 실리는 것). 항목별 동의 문서 다섯 개 — `consent-model.ts` 의 코드와 하나씩 짝이다.
 *
 * 규칙
 * - `TERMS_VERSION` 은 약관 내용이 바뀔 때마다 올린다. 사용자의 동의는 이 버전에 묶여 기록되고(서버 `consents`), 버전이 오르면 **다시 동의**를 받는다.
 *   ★서버 설정 `consent.terms_version`(`config/guardrails.yaml`)과 같은 값이어야 한다 — 다르면 서버가 409 `terms_version_changed` 로 거절한다.
 * - `TERMS_STATUS` 가 `draft` 인 동안 화면은 `DRAFT_NOTICE`(「AI 작성 초안 · 변호사 검토 전 · 운영 주체 정보 확정 전」)를 붙인다.
 *   법무 검토와 운영 주체 정보 확정이 끝나면 `reviewed` 로 바꾼다(시험이 그때 자리표시가 남았는지 본다).
 * - 한국어본이 정본이다. 영어본은 참고용 번역이다(각 문서의 마지막 조가 그렇게 말한다).
 * - ★본문은 **서비스가 실제로 하는 일만** 적는다. 근거(파일:줄)와 아직 서버에 없는 기능 표시는
 *   `wiki/records/plans/2026-10-05_약관_초안/00_법무확인_목록.md` 의 대조 표에 있다. 그 폴더의 01~05 는 이 파일의 한국어 본문 사본이다.
 * - ★정해지지 않은 값은 지어내지 않는다 — 본문에 「【확정 필요: …】」를 직접 쓰지 않고 `OPERATOR` · `RETENTION` 상수를 끼워 넣는다(시험이 지킨다).
 */
export const TERMS_VERSION = "2026-10-05.1";   // `[2026-10-05]` .1 = 운영 주체 · 문의 연락처 · 보호책임자를 채웠다(글이 바뀌었으니 버전을 올린다). 서버 `consent.terms_version` 과 같이 올린다
export const TERMS_STATUS: "draft" | "reviewed" = "draft";
/** 시행일("YYYY-MM-DD"). 확정 전에는 초안 작성일. */
export const TERMS_EFFECTIVE = "2026-10-05";

/**
 * 운영 주체 정보. ★확정되기 전에는 지어내지 않고 「【확정 필요: …】」 자리표시를 그대로 둔다 - 약관 본문은 이 값을 끼워 넣는다.
 * `[2026-10-05 사용자 지시]` 지금은 사업자가 아닌 부트캠프 최종 프로젝트(비영리)라 대표자 · 소재지는 「해당 없음」, 문의 연락처는 팀 공용 이메일이다.
 *   개인정보 보호책임자는 「성명 또는 부서의 명칭과 연락처」 중 하나로 적을 수 있다(개인정보 보호법 제30조 제1항 제6호, 2026-10-05 조문 확인). 사용자 지시(2026-10-05 「팀명만 나오면 되지 않아?」)로 **개인 이름은 공개 글에 넣지 않고** 팀 명칭 + 팀 이메일만 적는다.
 *   실제로 문의를 받아 처리하는 담당자는 팀 안에서 정해 둔다(공개하지 않음 — 운영자 화면이 생기면 거기에 내부 메모로). 위치정보 관리책임자도 같은 방식이다. 위치 저장 기능이 생기기 전에는 위치 약관을 시행하지 않는다.
 *   ★이 값은 나중에 운영자 화면에서 바꿀 수 있게 한다(서버 요청서 `2026-10-05_운영자_정보_입력_화면_백엔드_요청.md`) - 그 값이 오면 이 상수는 서버 값이 없을 때의 기본값이 된다.
 */
export const OPERATOR = {
  name: "A-COPilot 팀(부트캠프 최종 프로젝트 · 비영리)",
  representative: "해당 없음(사업자 아님)",
  address: "해당 없음(사업자 아님 · 연락은 이메일로)",
  contact: "acopilot3206@gmail.com",
  privacyOfficer: "A-COPilot 팀(개인정보 보호 문의 창구) · acopilot3206@gmail.com",
  locationOfficer: "A-COPilot 팀(위치정보 문의 창구) · acopilot3206@gmail.com",
} as const;

/** [한국어, English] */
export type Bilingual = readonly [ko: string, en: string];

/**
 * 보유 · 이용 기간. 약관 본문은 이 값을 끼워 넣는다.
 * - 서버 코드 · 설정으로 확인한 값은 그 값을 쓰고 근거를 주석에 적는다.
 * - ★정해지지 않은 값은 「【확정 필요: …】」 + 「추천값(확정 전)」으로 둔다 — 사용자(운영 주체)가 정하면 값만 바꾼다(정하면 `TERMS_VERSION` 을 올린다).
 */
export const RETENTION = {
  /** 근거: `config/guardrails.yaml` `web_guard.guest_idle_hours: 168` · `guest.trip_grace_days: 3` · `guest.trip_keep_max_days: 180`, 계산 `travel_ops/modules/web_account/guest_cleanup.py:8-10,88`. */
  guestData: [
    "마지막 이용 후 7일(아직 끝나지 않은 여행 일정이 있으면 그 일정이 끝난 뒤 3일까지 두되, 마지막 이용 후 183일을 넘기지 않음)",
    "7 days after the last use (if a trip has not ended yet, until 3 days after it ends, but never more than 183 days after the last use)",
  ],
  /** 근거: `web_cookie.py:57-68`(게스트 쿠키는 `Max-Age` 없음) · `guardrails.yaml` `web_guard.guest_idle_hours: 168`. */
  guestSession: [
    "브라우저를 닫을 때까지(서버 쪽 세션도 마지막 이용 후 7일이 지나면 끝남)",
    "until the browser is closed (the server-side session also ends 7 days after the last use)",
  ],
  /** 근거: `guardrails.yaml` `web_guard.member_idle_hours: 168` · `session_max_hours: 720`. */
  memberSession: [
    "마지막 이용 후 7일, 로그인한 때부터 최장 30일 동안",
    "up to 7 days after the last use and at most 30 days after signing in",
  ],
  /** 서버에 회원 자료의 보관 기한 규칙이 없다(회원은 게스트 정리 대상이 아니다 — `guest_cleanup.py:6`). */
  memberData: [
    "【확정 필요: 회원의 여행 · 대화 기록 보관 기간 — 추천값(확정 전): 회원이 지우거나 탈퇴를 요청할 때까지, 다만 마지막 이용 후 1년이 지나면 파기】",
    "【확정 필요: 회원의 여행 · 대화 기록 보관 기간】 (to be decided — recommended, not yet confirmed: until the member deletes it or asks to leave, and destroyed 1 year after the last use)",
  ],
  /** 여행을 지워도 처리 기록(Case)은 남는다 — `trip_delete.py:10`, 채팅 문장이 Case 에 실린다 — `trip_messages.py:570-574`. 보관 기한 규칙 없음. */
  caseRecords: [
    "【확정 필요: 처리 기록(질문 문장과 처리 경과) 보관 기간 — 지금은 여행을 지워도 남음. 추천값(확정 전): 여행이 지워지거나 게스트 자료가 지워질 때 함께 파기】",
    "【확정 필요: 처리 기록 보관 기간】 (to be decided — currently kept even after the trip is deleted; recommended, not yet confirmed: destroyed together with the trip or the guest's data)",
  ],
  /** 근거: `guardrails.yaml` `web_guard.ip_retention_hours: 48`, 지우는 곳 `web_guard.py:296-305`, 날짜를 섞은 HMAC `web_guard.py:170-173`. */
  abuseIpToken: ["48시간", "48 hours"],
  /** 근거: `guardrails.yaml` `web_guard.usage_retention_days: 35`, `web_guard.py:301-307`. */
  usageCounts: ["35일", "35 days"],
  /** 서버 설정 `consent.evidence_retention_days: 1825`(기록한 때부터 계산 — `consents.py:186-193`). 요청서는 「서비스 종료 후 5년」을 추천했다 — 기준 시점이 다르다. */
  consentRecords: [
    "【확정 필요: 동의 기록 보관 기간 — 추천값(확정 전): 기록한 때부터 5년(지금 서버 설정 1,825일)】",
    "【확정 필요: 동의 기록 보관 기간】 (to be decided — recommended, not yet confirmed: 5 years from the time of recording; the server is currently set to 1,825 days)",
  ],
  /** 요청서 `2026-10-05_동의기록_위치수집_백엔드_요청.md` 「정할 것」 추천값. 서버 구현 전. */
  locationPoints: [
    "【확정 필요: 위치 점 · 머문 지점 보관 기간 — 추천값(확정 전): 여행이 끝난 뒤 7일】",
    "【확정 필요: 위치 점 · 머문 지점 보관 기간】 (to be decided — recommended, not yet confirmed: 7 days after the trip ends)",
  ],
  /**
   * 위치정보법 제16조 제2항의 이용 · 제공사실 확인자료. 법에는 기간이 없고, 고시 「위치정보의 관리적·기술적 보호조치 기준」(방송통신위원회고시 제2022-11호)
   * 제6조 제5항이 취급대장을 「최소 6개월 이상」 보관하라고 한다(조사 2026-10-05, 고시 최신판 여부는 미확인). 동의를 철회하면 같은 법 제24조 제4항에 따라 지체 없이 파기한다. 서버 구현 전.
   */
  locationFactLog: [
    "【확정 필요: 위치정보 이용 · 제공사실 확인자료 보관 기간 — 추천값(확정 전): 기록한 때부터 6개월(관련 고시의 최소 보관 기간)】",
    "【확정 필요: 위치정보 이용 · 제공사실 확인자료 보관 기간】 (to be decided — recommended, not yet confirmed: 6 months from recording, the minimum in the related public notice)",
  ],
} as const satisfies Record<string, Bilingual>;

export interface TermsSection {
  heading: Bilingual;
  /** 문단은 빈 줄로 나눈다. 줄이 「- 」로 시작하면 목록이다. */
  body: Bilingual;
}

export interface TermsDoc {
  code: ConsentCode;
  required: boolean;
  title: Bilingual;
  /** 동의 카드에 보이는 두세 줄 요약. */
  summary: Bilingual;
  sections: readonly TermsSection[];
}

/** `TERMS_STATUS` 가 `draft` 인 동안 약관 화면 맨 위에 붙이는 표시. */
export const DRAFT_NOTICE: Bilingual = [
  "AI 작성 초안 · 변호사 검토 전 · 운영 주체 정보 확정 전 — 이 문서만으로는 법적 효력이 보장되지 않습니다.",
  "AI-written draft · not yet reviewed by a lawyer · operator details not yet confirmed — this document alone does not guarantee legal effect.",
];

// ── 본문 조립 도우미 ─────────────────────────────────────────────
/** 문단을 빈 줄로 잇는다. */
const paras = (...parts: string[]): string => parts.join("\n\n");
/** 목록 — 줄마다 「- 」로 시작한다. */
const list = (...items: string[]): string => items.map((item) => `- ${item}`).join("\n");

/** 모든 문서의 마지막 조 — 한국어본이 정본이다. */
const LANGUAGE_SECTION: TermsSection = {
  heading: ["언어", "Language"],
  body: [
    "이 문서는 한국어본이 정본입니다. 영어본은 이해를 돕기 위한 참고용 번역이며, 두 본의 내용이 다르면 한국어본이 우선합니다.",
    "The Korean version of this document is the official text. The English version is a translation for reference only; if the two differ, the Korean version prevails.",
  ],
};

const serviceTerms: TermsDoc = {
  code: "service_terms",
  required: true,
  title: ["triPilot 서비스 이용약관", "triPilot Terms of Service"],
  summary: [
    "triPilot은 올리신 여행 계획을 읽고 확인하며, 회원의 여행은 끝날 때까지 지켜보고 바뀐 점을 알려 드립니다. 대신 예약하거나 결제하지 않습니다. 동의하지 않으면 서비스를 이용할 수 없습니다.",
    "triPilot reads and checks the travel plan you upload and, for members, watches the trip until it ends and tells you what changed. It does not book or pay for anything on your behalf. You cannot use the service without agreeing.",
  ],
  sections: [
    {
      heading: ["제1조 (목적)", "Article 1 (Purpose)"],
      body: [
        `이 약관은 ${OPERATOR.name}(이하 「운영자」)가 제공하는 triPilot 서비스를 이용하는 조건과 절차, 운영자와 이용자의 권리와 의무를 정합니다.`,
        `These terms set out the conditions and procedures for using the triPilot service provided by ${OPERATOR.name} (the "Operator"), and the rights and obligations of the Operator and users.`,
      ],
    },
    {
      heading: ["제2조 (정의)", "Article 2 (Definitions)"],
      body: [
        paras(
          "이 약관에서 쓰는 말의 뜻은 다음과 같습니다. triPilot의 다른 동의 문서(개인정보 · 민감정보 · 개인위치정보 · 알림 채널)도 같은 뜻으로 씁니다.",
          list(
            "「서비스」: 이용자가 올린 여행 계획을 읽고 확인하며, 등록한 여행을 여행이 끝날 때까지 지켜보고 알리는 triPilot 웹 서비스와 그에 딸린 API를 말합니다.",
            "「이용자」: 이 약관에 동의하고 서비스를 이용하는 사람을 말합니다. 이용자는 게스트와 회원으로 나뉩니다.",
            "「게스트」: 소셜 계정을 연결하지 않고 서비스를 이용하는 이용자를 말합니다.",
            "「회원」: 소셜 계정(현재는 구글 계정)을 연결한 이용자를 말합니다.",
            "「여행 계획」: 이용자가 글 · 파일 · 사진으로 올리거나 서비스에 짜 달라고 요청해 만든 일정과, 그 안의 장소 · 시각 · 인원 · 예산 · 예약 표시 같은 내용을 말합니다.",
            "「여행계획서 링크」: 여행마다 만들어지는 주소로, 로그인 없이 그 여행의 최신 일정을 볼 수 있는 링크를 말합니다.",
            "「알림 채널」: 이용자가 연결한 디스코드 웹훅처럼 서비스가 이용자에게 알림을 보내는 곳을 말합니다.",
            "「에이전트 키」: 회원이 자기 AI 에이전트 같은 다른 프로그램이 서비스 API를 쓰게 하려고 만드는 접속 키를 말합니다.",
          ),
        ),
        paras(
          "The words below have these meanings in these terms and in triPilot's other consent documents (personal data, sensitive data, personal location data and alert channel).",
          list(
            "\"Service\": the triPilot web service and its APIs, which read and check the travel plan a user uploads and watch a registered trip until it ends and send alerts.",
            "\"User\": a person who has agreed to these terms and uses the Service. Users are either guests or members.",
            "\"Guest\": a user who uses the Service without connecting a social account.",
            "\"Member\": a user who has connected a social account (currently a Google account).",
            "\"Travel plan\": a schedule a user uploads as text, files or photos or asks the Service to draft, including the places, times, party size, budget and booking notes in it.",
            "\"Trip plan link\": an address created for each trip that shows the trip's latest schedule without signing in.",
            "\"Alert channel\": a place the Service sends alerts to, such as a Discord webhook the user has connected.",
            "\"Agent key\": an access key a member creates so that another program, such as the member's own AI agent, can use the Service API.",
          ),
        ),
      ],
    },
    {
      heading: ["제3조 (약관의 게시와 변경)", "Article 3 (Posting and changing these terms)"],
      body: [
        paras(
          "① 운영자는 이 약관을 서비스 화면에 게시해, 이용자가 언제든 볼 수 있게 해야 합니다.",
          "② 운영자는 관계 법령을 어기지 않는 범위에서 이 약관을 바꿀 수 있습니다.",
          "③ 운영자는 약관을 바꿀 때 바뀌는 내용과 시행일을 시행일 7일 전부터 서비스 화면에 알려야 합니다. 이용자에게 불리하게 바뀌는 경우에는 시행일 30일 전부터 알려야 합니다.",
          "④ 약관이 바뀌면 이용자는 바뀐 약관에 다시 동의해야 서비스를 계속 이용할 수 있습니다. 다시 동의하지 않는 이용자는 이용을 그만둘 수 있고, 제17조(이용 종료)에 따라 자기 자료의 삭제를 요청할 수 있습니다.",
        ),
        paras(
          "(1) The Operator must post these terms on the Service screens so that users can read them at any time.",
          "(2) The Operator may change these terms to the extent permitted by law.",
          "(3) When changing the terms, the Operator must announce the changes and their effective date on the Service screens at least 7 days before the effective date, or at least 30 days before if the change is unfavourable to users.",
          "(4) When the terms change, a user must agree to the new terms again to keep using the Service. A user who does not agree may stop using the Service and may ask for their data to be deleted under Article 17 (Ending use).",
        ),
      ],
    },
    {
      heading: ["제4조 (서비스 내용)", "Article 4 (What the Service does)"],
      body: [
        paras(
          "운영자는 다음 서비스를 제공합니다.",
          list(
            "여행 계획 읽기: 이용자가 올린 글 · 파일 · 사진에서 일정, 장소, 시각을 읽어 냅니다.",
            "여행 계획 확인: 장소가 실제로 있는지, 그 시각에 여는지, 장소 사이 이동 시간이 맞는지를 공개된 정보와 지도 정보로 확인합니다.",
            "일정 짜기: 이용자가 요청하면 조건에 맞는 일정 초안을 만듭니다.",
            "여행 지켜보기와 알림(회원만): 등록한 여행을 여행이 끝날 때까지 날씨 · 재난 · 장소 운영 정보 등으로 지켜보고, 일정에 문제가 생기면 제6조(일정 변경과 되돌리기)에 따라 일정을 바꾸거나 바꿀지 묻고 그 사실을 알립니다.",
            "여행 중 질문 답변: 채팅으로 일정 · 장소 · 가는 길을 묻는 말에 답합니다.",
            "여행계획서 링크와 계획서 내려받기.",
            "에이전트 키로 쓰는 API(회원만): 회원의 AI 에이전트가 그 회원의 여행만 읽거나 고칠 수 있게 합니다.",
          ),
          "서비스는 인공지능(언어 모델)을 써서 여행 계획을 읽고, 일정을 짜고, 채팅에 답합니다.",
        ),
        paras(
          "The Operator provides the following.",
          list(
            "Reading travel plans: the Service reads the schedule, places and times from the text, files or photos a user uploads.",
            "Checking travel plans: the Service uses public information and map information to check whether places exist, whether they are open at the planned times, and whether the travel times between them work.",
            "Drafting schedules: on request, the Service drafts a schedule that fits the user's conditions.",
            "Watching trips and sending alerts (members only): the Service watches a registered trip until it ends, using weather, disaster and venue information among others; if a problem affects the schedule, it changes the schedule or asks first under Article 6 (Schedule changes and undoing them) and tells the user.",
            "Answering questions during the trip: the Service answers chat questions about the schedule, places and directions.",
            "Trip plan links and downloading the plan.",
            "API access with an agent key (members only): a member's AI agent can read or change only that member's trips.",
          ),
          "The Service uses artificial intelligence (language models) to read travel plans, draft schedules and answer chat messages.",
        ),
      ],
    },
    {
      heading: ["제5조 (서비스가 하지 않는 일)", "Article 5 (What the Service does not do)"],
      body: [
        paras(
          "① 서비스는 이용자를 대신해 숙소 · 식당 · 시설 · 교통편을 예약하거나, 예약을 바꾸거나 취소하지 않습니다. 결제를 받거나 대신하지도 않습니다.",
          "② 운영자는 이용자와 업체(숙소 · 식당 · 시설 · 교통 사업자 등) 사이 계약의 당사자가 아닙니다. 예약 · 결제 · 환불은 이용자와 그 업체 사이에서 정해집니다.",
          "③ 이 약관에서 서비스가 「일정을 바꾼다」는 것은 서비스 안의 여행 일정을 바꾼다는 뜻입니다. 업체의 예약은 바뀌지 않습니다.",
        ),
        paras(
          "(1) The Service does not book, change or cancel accommodation, restaurants, venues or transport for the user. It does not take or make payments.",
          "(2) The Operator is not a party to any contract between the user and a business (accommodation, restaurant, venue, transport operator and so on). Bookings, payments and refunds are a matter between the user and that business.",
          "(3) In these terms, the Service \"changing the schedule\" means changing the trip schedule inside the Service. Bookings with businesses are not changed.",
        ),
      ],
    },
    {
      heading: ["제6조 (일정 변경과 되돌리기)", "Article 6 (Schedule changes and undoing them)"],
      body: [
        paras(
          "① 회원이 등록한 여행에 문제(날씨 · 재난 · 장소 휴무 등)가 생기면, 서비스는 이용자가 여행 취향 설문의 「갑자기 일정이 꼬이면」 문항에서 고른 방식에 따라 다음과 같이 합니다.",
          list(
            "「먼저 물어봐줘」를 고른 경우: 서비스는 일정을 바꾸기 전에 이용자에게 묻습니다. 안전에 관한 사건(지진 · 재난 문자 · 기상 경보 등)은 바로 알립니다.",
            "그 밖의 경우: 서비스는 고른 대체 일정을 먼저 반영하고 알립니다. 다만 원인이 날씨뿐이면, 이용자가 「비슷한 곳으로 바꿔줘」를 직접 고른 경우에만 먼저 반영하고, 그렇지 않으면 바꾸기 전에 묻습니다.",
          ),
          "② 이용자가 고정하거나 잠근 일정, 여행 계획에 예약 번호가 적힌 일정은 서비스가 묻지 않고 바꾸지 않습니다.",
          "③ 이용자는 서비스가 반영한 변경을 채팅 · 웹 화면 · API로 되돌리거나 다른 안으로 바꿔 달라고 요청할 수 있습니다.",
          "④ 알림은 승인 요청이 아닙니다. 이용자가 알림을 보지 못해도 여행계획서 링크와 웹 화면에서 최신 일정을 볼 수 있습니다.",
          "⑤ 게스트의 여행은 지켜보기와 알림 대상이 아닙니다.",
        ),
        paras(
          "(1) If a problem (weather, a disaster, a venue closure and so on) affects a trip a member has registered, the Service acts according to the answer the user chose for \"If plans suddenly go wrong\" in the travel preference questions:",
          list(
            "\"Ask me first\": the Service asks the user before changing the schedule. Safety events (earthquakes, emergency alerts, weather warnings and so on) are sent at once.",
            "Otherwise: the Service applies the alternative it chose first and then tells the user. If the only cause is the weather, however, the Service applies the change first only when the user directly chose \"Swap in something similar\"; otherwise it asks before changing.",
          ),
          "(2) The Service does not change, without asking, an item the user has pinned or locked, or an item for which the travel plan contains a booking number.",
          "(3) The user may ask, by chat, on the web screens or through the API, to undo a change the Service applied or to switch to another option.",
          "(4) Alerts are not requests for approval. Even if the user misses an alert, the latest schedule is shown on the trip plan link and the web screens.",
          "(5) Guests' trips are not watched and do not receive alerts.",
        ),
      ],
    },
    {
      heading: ["제7조 (이용 계약의 성립과 나이)", "Article 7 (Forming the agreement, and age)"],
      body: [
        paras(
          "① 이용 계약은 이용자가 이 약관과 「개인정보 수집 · 이용 동의 및 처리방침」에 모두 동의하면 성립합니다. 두 문서는 필수 동의입니다.",
          "② 이용자가 필수 동의를 하지 않거나 철회하면 서비스를 이용할 수 없습니다.",
          "③ 민감정보, 개인위치정보, 알림 채널 정보에 대한 동의는 선택입니다. 이용자가 선택 동의를 하지 않아도 서비스를 이용할 수 있으며, 그 동의가 필요한 기능만 쓸 수 없습니다.",
          "④ 만 14세 미만인 사람은 서비스를 이용할 수 없습니다. 이용자는 동의할 때 자신이 만 14세 이상임을 확인해야 합니다.",
        ),
        paras(
          "(1) The agreement is formed when the user agrees to both these terms and the \"Consent to Collection and Use of Personal Data and Privacy Policy\". Both are required.",
          "(2) A user who does not give, or withdraws, a required consent cannot use the Service.",
          "(3) Consent for sensitive data, personal location data and alert channel data is optional. A user who does not give an optional consent can still use the Service; only the features that need that consent are unavailable.",
          "(4) People under 14 years of age may not use the Service. When agreeing, the user must confirm that they are at least 14 years old.",
        ),
      ],
    },
    {
      heading: ["제8조 (게스트와 회원)", "Article 8 (Guests and members)"],
      body: [
        paras(
          "① 게스트에게는 다음이 적용됩니다.",
          list(
            "로그인 없이 바로 이용하며, 브라우저를 닫으면 로그인 상태가 끝납니다.",
            "여행은 1개까지 만들 수 있고, 여행 지켜보기와 알림은 제공되지 않습니다.",
            `게스트의 자료는 보관 기간(${RETENTION.guestData[0]})이 지나면 지워지며 되살릴 수 없습니다. 이용자는 필요한 계획서를 미리 내려받아 두어야 합니다.`,
          ),
          `② 구글 계정을 연결하면 회원이 됩니다. 회원의 로그인 상태는 ${RETENTION.memberSession[0]} 유지됩니다(그 뒤에는 다시 로그인해야 합니다). 회원은 여행 지켜보기와 알림, 에이전트 키를 쓸 수 있습니다.`,
        ),
        paras(
          "(1) The following applies to guests.",
          list(
            "Guests use the Service without signing in; the signed-in state ends when the browser is closed.",
            "A guest can create one trip, and trips are not watched and do not receive alerts.",
            `A guest's data is deleted when its retention period (${RETENTION.guestData[1]}) has passed, and cannot be restored. The user must download any plan they need beforehand.`,
          ),
          `(2) Connecting a Google account makes the user a member. A member stays signed in for ${RETENTION.memberSession[1]}. Members can use trip watching, alerts and agent keys.`,
        ),
      ],
    },
    {
      heading: ["제9조 (이용자의 의무)", "Article 9 (Users' obligations)"],
      body: [
        paras(
          "① 이용자는 다음 일을 해서는 안 됩니다.",
          list(
            "다른 사람의 세션이나 에이전트 키를 쓰는 일",
            "자동화된 대량 요청 등으로 서비스 운영을 방해하거나, 서비스가 정한 이용 한도를 피하려는 일",
            "법령에 어긋나는 내용을 올리는 일",
            "서비스에서 보여 주는 공공데이터 · 지도 정보를 그 제공자의 이용 조건에 어긋나게 쓰는 일",
          ),
          "② 이용자가 동행자 등 다른 사람의 개인정보를 여행 계획이나 채팅에 넣으려면, 그 사람에게 미리 알리고 동의를 받아야 합니다.",
          "③ 회원은 에이전트 키를 남에게 알려서는 안 되며, 키가 새었다고 생각되면 바로 폐기해야 합니다.",
          "④ 여행계획서 링크를 받은 사람은 누구나 로그인 없이 그 여행의 일정을 볼 수 있습니다. 이용자는 이 점을 알고 링크를 공유해야 합니다.",
        ),
        paras(
          "(1) The user must not:",
          list(
            "use another person's session or agent key;",
            "disrupt the Service with automated mass requests or similar, or try to get around the usage limits the Service sets;",
            "upload content that breaks the law;",
            "use the public data or map information shown by the Service against the terms of its provider.",
          ),
          "(2) Before putting another person's personal data, such as a travel companion's, into a travel plan or chat, the user must tell that person and get their consent.",
          "(3) A member must not share an agent key with anyone and must revoke it at once if they believe it has leaked.",
          "(4) Anyone who receives a trip plan link can see that trip's schedule without signing in. The user must keep this in mind when sharing the link.",
        ),
      ],
    },
    {
      heading: ["제10조 (이용 제한)", "Article 10 (Restrictions on use)"],
      body: [
        paras(
          "① 운영자는 서비스를 안정적으로 제공하기 위해 이용 한도(예: 하루 요청 수)를 둘 수 있고, 사람인지 확인하는 절차를 요청할 수 있습니다.",
          "② 이용자가 제9조(이용자의 의무)를 어기면 운영자는 그 이용을 막거나 세션 · 에이전트 키를 거둘 수 있습니다. 운영자는 그 사유를 서비스 화면으로 알려야 하며, 급한 경우에는 막은 뒤에 알릴 수 있습니다.",
        ),
        paras(
          "(1) To keep the Service stable, the Operator may set usage limits (for example, a number of requests per day) and may ask the user to complete a check that they are human.",
          "(2) If a user breaks Article 9 (Users' obligations), the Operator may block that use or revoke the session or agent key. The Operator must explain the reason on the Service screens, and in urgent cases may do so after blocking.",
        ),
      ],
    },
    {
      heading: ["제11조 (정보의 한계와 이용자의 확인)", "Article 11 (Limits of the information and the user's own checks)"],
      body: [
        paras(
          "① 서비스가 쓰는 운영시간 · 휴무일 · 장소 정보 · 이동 시간 · 날씨 같은 정보는 한국관광공사 공공데이터, 지도 · 장소 서비스, 기상 정보 등 외부에서 받은 정보입니다. 이 정보는 늦게 반영되거나 실제와 다를 수 있습니다.",
          "② 이동 시간은 계산한 추정값이며 실제 교통 상황과 다를 수 있습니다.",
          "③ 화면의 예약 표시는 이용자가 입력한 내용을 기준으로 하며, 서비스는 업체의 예약 상태를 확인하지 않습니다. 이용자는 방문 · 예약 전에 해당 업체의 최신 안내를 직접 확인해야 합니다.",
          "④ 서비스는 확인하지 못한 정보를 확인한 것처럼 알리지 않습니다.",
          "⑤ 알림은 메신저 업체의 장애나 알림 채널의 해제 · 삭제 때문에 늦거나 닿지 않을 수 있습니다. 여행의 최신 상태는 여행계획서 링크와 웹 화면이 기준입니다.",
          "⑥ 여행 계획 읽기 · 일정 짜기 · 채팅 답변은 인공지능이 만든 결과라 원문이나 사실과 다를 수 있습니다. 이용자는 여행을 등록하기 전 확인 화면에서 읽어 낸 일정을 확인하고 고칠 수 있습니다.",
        ),
        paras(
          "(1) Information the Service uses, such as opening hours, closing days, place details, travel times and weather, comes from outside sources such as Korea Tourism Organization public data, map and place services and weather information. It may be out of date or differ from reality.",
          "(2) Travel times are calculated estimates and may differ from actual traffic.",
          "(3) Booking notes on screen reflect what the user entered; the Service does not check a business's booking records. The user must check the business's latest information before visiting or booking.",
          "(4) The Service does not present information it could not confirm as confirmed.",
          "(5) Alerts may be late or may not arrive because of a messenger provider's outage or because an alert channel was disconnected or deleted. The trip plan link and the web screens show the trip's current state.",
          "(6) Plan reading, schedule drafting and chat answers are produced by artificial intelligence and may differ from the source or from the facts. Before registering a trip, the user can review and correct the schedule that was read on the review screen.",
        ),
      ],
    },
    {
      heading: ["제12조 (서비스의 변경과 중단)", "Article 12 (Changing or suspending the Service)"],
      body: [
        paras(
          "① 운영자는 점검, 설비 장애, 외부 정보 제공자의 장애나 이용 조건 변경, 그 밖의 운영상 이유로 서비스의 전부 또는 일부를 바꾸거나 멈출 수 있습니다.",
          "② 운영자는 미리 알릴 수 있는 변경 · 중단을 서비스 화면에 미리 알려야 하며, 미리 알릴 수 없었던 경우에는 그 뒤에 지체 없이 알려야 합니다.",
          "③ 운영자가 서비스를 끝낼 때는 이용자가 자기 계획서를 내려받을 수 있도록 미리 알려야 하며, 남은 개인정보는 「개인정보 수집 · 이용 동의 및 처리방침」에 따라 파기해야 합니다.",
        ),
        paras(
          "(1) The Operator may change or suspend all or part of the Service for maintenance, equipment failure, an outage or change of terms at an outside information provider, or other operational reasons.",
          "(2) The Operator must announce changes or suspensions on the Service screens in advance where possible, and without delay afterwards where advance notice was not possible.",
          "(3) Before ending the Service, the Operator must give notice so that users can download their plans, and must destroy the remaining personal data under the \"Consent to Collection and Use of Personal Data and Privacy Policy\".",
        ),
      ],
    },
    {
      heading: ["제13조 (요금)", "Article 13 (Fees)"],
      body: [
        "서비스는 현재 무료로 제공됩니다. 운영자가 유료 기능을 도입하려면 요금과 조건을 미리 알리고 이용자의 별도 동의를 받아야 하며, 동의하지 않은 이용자에게 요금을 청구해서는 안 됩니다.",
        "The Service is currently free. Before introducing paid features, the Operator must announce the fees and conditions in advance and obtain the user's separate consent, and must not charge a user who has not agreed.",
      ],
    },
    {
      heading: ["제14조 (책임의 제한)", "Article 14 (Limits of liability)"],
      body: [
        paras(
          "① 운영자는 고의 또는 과실로 이용자에게 손해를 끼친 경우 관계 법령에 따라 배상합니다.",
          "② 운영자는 다음 손해에 대해서는, 운영자에게 고의 또는 과실이 없는 한 책임지지 않습니다.",
          list(
            "외부 정보(공공데이터 · 지도 · 날씨 등)가 늦게 반영되거나 틀려서 생긴 손해",
            "이용자가 업체의 예약 · 운영 정보를 직접 확인하지 않아 생긴 손해",
            "천재지변, 통신망 장애, 메신저 업체의 장애처럼 운영자가 막을 수 없는 사유로 생긴 손해",
            "이용자가 세션 · 에이전트 키 · 여행계획서 링크를 소홀히 관리해 생긴 손해",
          ),
          "③ 이 조는 운영자의 고의 또는 중대한 과실로 생긴 손해에 대한 책임을 줄이거나 없애지 않습니다.",
        ),
        paras(
          "(1) The Operator compensates the user under applicable law for damage it causes intentionally or negligently.",
          "(2) Unless the Operator acted intentionally or negligently, it is not liable for:",
          list(
            "damage caused by outside information (public data, maps, weather and so on) being out of date or wrong;",
            "damage caused by the user not checking a business's booking or opening information directly;",
            "damage caused by events the Operator cannot prevent, such as natural disasters, network failures or a messenger provider's outage;",
            "damage caused by the user's careless handling of their session, agent key or trip plan link.",
          ),
          "(3) This article does not reduce or exclude the Operator's liability for damage caused by its intent or gross negligence.",
        ),
      ],
    },
    {
      heading: ["제15조 (권리의 귀속과 출처 표시)", "Article 15 (Rights and attribution)"],
      body: [
        paras(
          "① 서비스의 화면과 프로그램에 대한 권리는 운영자 또는 정당한 권리자에게 있습니다.",
          "② 이용자가 올린 여행 계획에 대한 권리는 이용자에게 있습니다. 운영자는 이를 이 약관과 「개인정보 수집 · 이용 동의 및 처리방침」에서 정한 목적에만 씁니다.",
          "③ 서비스가 보여 주는 관광 정보에는 한국관광공사의 공공데이터가 들어 있으며, 서비스는 그 출처를 「ⓒ한국관광공사」로 표시합니다. 지도는 OpenStreetMap 등 지도 제공자의 자료를 쓰며 각 제공자가 정한 출처 표시를 따릅니다.",
        ),
        paras(
          "(1) Rights in the Service's screens and software belong to the Operator or the lawful rights holder.",
          "(2) Rights in the travel plans a user uploads belong to the user. The Operator uses them only for the purposes set out in these terms and the \"Consent to Collection and Use of Personal Data and Privacy Policy\".",
          "(3) Tourism information shown by the Service includes Korea Tourism Organization public data, credited as \"ⓒKorea Tourism Organization\". Maps use data from map providers such as OpenStreetMap, credited as each provider requires.",
        ),
      ],
    },
    {
      heading: ["제16조 (통지)", "Article 16 (Notices)"],
      body: [
        "운영자는 이용자 전체에게 알릴 일은 서비스 화면에 게시해 알리고, 개별 이용자에게 알릴 일은 서비스 화면이나 그 이용자가 연결한 알림 채널로 알립니다.",
        "The Operator gives notices to all users by posting them on the Service screens, and notices to an individual user on the Service screens or through the alert channel that user has connected.",
      ],
    },
    {
      heading: ["제17조 (이용 종료)", "Article 17 (Ending use)"],
      body: [
        paras(
          "① 이용자는 언제든 이용을 그만둘 수 있습니다. 여행 삭제, 소셜 계정 연결 해제, 에이전트 키 폐기, 선택 동의 철회는 서비스 화면에서 직접 할 수 있습니다.",
          `② 회원 자료 전체의 삭제 등 서비스 화면에서 할 수 없는 요청은 문의처(${OPERATOR.contact})로 할 수 있으며, 운영자는 관계 법령이 정한 기간 안에 처리해야 합니다.`,
          "③ 이용자가 필수 동의를 철회하면 서비스를 이용할 수 없게 됩니다.",
        ),
        paras(
          "(1) The user may stop using the Service at any time. Deleting a trip, disconnecting a social account, revoking an agent key and withdrawing an optional consent can be done directly on the Service screens.",
          `(2) Requests that cannot be made on the Service screens, such as deleting all of a member's data, may be sent to ${OPERATOR.contact}, and the Operator must handle them within the period set by law.`,
          "(3) If the user withdraws a required consent, the user can no longer use the Service.",
        ),
      ],
    },
    {
      heading: ["제18조 (준거법과 관할)", "Article 18 (Governing law and jurisdiction)"],
      body: [
        paras(
          "① 이 약관은 대한민국 법에 따라 해석합니다.",
          "② 서비스 이용으로 생긴 분쟁에 관한 소송은 민사소송법에 따른 관할 법원에 제기합니다.",
        ),
        paras(
          "(1) These terms are governed by the laws of the Republic of Korea.",
          "(2) Lawsuits over disputes arising from use of the Service are brought before the court with jurisdiction under the Civil Procedure Act.",
        ),
      ],
    },
    {
      heading: ["부칙 및 운영자 정보", "Supplementary provision and operator details"],
      body: [
        paras(
          `이 약관은 ${TERMS_EFFECTIVE}부터 시행합니다(약관 버전 ${TERMS_VERSION}).`,
          list(
            `운영자: ${OPERATOR.name}`,
            `대표자: ${OPERATOR.representative}`,
            `소재지: ${OPERATOR.address}`,
            `문의: ${OPERATOR.contact}`,
          ),
        ),
        paras(
          `These terms take effect on ${TERMS_EFFECTIVE} (terms version ${TERMS_VERSION}).`,
          list(
            `Operator: ${OPERATOR.name}`,
            `Representative: ${OPERATOR.representative}`,
            `Address: ${OPERATOR.address}`,
            `Contact: ${OPERATOR.contact}`,
          ),
        ),
      ],
    },
    LANGUAGE_SECTION,
  ],
};

const privacy: TermsDoc = {
  code: "privacy",
  required: true,
  title: ["개인정보 수집 · 이용 동의 및 개인정보 처리방침 (필수)", "Consent to Collection and Use of Personal Data and Privacy Policy (required)"],
  summary: [
    "서비스를 쓰려면 여행 계획 · 채팅 · 로그인 상태 같은 꼭 필요한 정보를 처리하는 데 동의해야 합니다. 이 정보는 여행을 확인하고 지켜보고 답하는 데 쓰며, 제3자에게 제공하지 않습니다. 동의하지 않으면 서비스를 이용할 수 없습니다.",
    "To use the Service you must agree to the processing of the information it needs, such as your travel plans, chat messages and sign-in state. It is used to check and watch your trips and answer you, and is not disclosed to third parties. Without this consent you cannot use the Service.",
  ],
  sections: [
    {
      heading: ["제1조 (이 문서에 대하여)", "Article 1 (About this document)"],
      body: [
        paras(
          `${OPERATOR.name}(이하 「운영자」)는 triPilot 서비스에서 이용자의 개인정보를 이 문서에 따라 처리합니다. 이 문서에서 쓰는 말의 뜻은 「triPilot 서비스 이용약관」 제2조(정의)와 같습니다.`,
          "제2조와 제3조는 꼭 필요한 정보의 수집 · 이용에 대한 동의 내용이고, 제4조부터는 개인정보 처리방침입니다. 민감정보, 개인위치정보, 알림 채널 정보는 이 문서가 아니라 각각의 선택 동의 문서가 정합니다.",
        ),
        paras(
          `${OPERATOR.name} (the "Operator") processes users' personal data in the triPilot service as described in this document. Words used here have the meanings given in Article 2 (Definitions) of the "triPilot Terms of Service".`,
          "Articles 2 and 3 are the consent to collect and use the information the Service needs; Article 4 onwards is the privacy policy. Sensitive data, personal location data and alert channel data are governed not by this document but by their own optional consent documents.",
        ),
      ],
    },
    {
      heading: ["제2조 (수집 · 이용하는 필수 정보와 목적, 보유 기간)", "Article 2 (Required information, purposes and retention)"],
      body: [
        paras(
          "운영자는 다음 정보를 적힌 목적에만 쓰고, 적힌 기간 동안만 보관합니다.",
          list(
            `이용 상태 정보 — 항목: 서비스가 만든 무작위 이용자 번호, 로그인 세션 쿠키(서버에는 원래 값 대신 해시값만 저장). 목적: 로그인 상태 유지, 요청이 본인에게서 왔는지 확인. 기간: 세션은 게스트 ${RETENTION.guestSession[0]}, 회원 ${RETENTION.memberSession[0]}. 이용자 번호는 아래 여행 정보와 같은 기간.`,
            "여행 정보 — 항목: 여행 계획 원문(붙여 넣은 글, 파일 · 사진에서 읽어 낸 글과 파일 이름. 올린 파일 자체는 저장하지 않음), 읽어 낸 일정(장소 · 시각 · 인원 · 예산 · 예약 번호 등 계획에 적힌 내용), 여행 취향 설문 답(여행 테마, 동행 구성과 직접 적은 동행 설명, 우선순위, 실내 · 실외, 일정이 꼬일 때 방식, 여유), 그 밖에 이용자가 준 여행 조건, 일정 변경 기록. 목적: 계획 읽기 · 확인, 일정 짜기, 여행 지켜보기와 알림, 여행계획서 링크.",
            "채팅 정보 — 항목: 이용자의 질문과 서비스의 답, 그 질문을 처리한 기록(처리 기록). 목적: 질문에 답하기, 일정 변경과 되돌리기 처리, 잘못된 처리 확인.",
            "회원 정보(구글 계정을 연결한 경우) — 항목: 구글 계정 고유 번호를 서버 비밀값으로 바꾼 값, 연결 시각. 구글 계정의 이메일 · 이름 · 사진은 받지 않습니다. 목적: 회원 로그인. 기간: 연결을 풀 때까지.",
            "에이전트 키 정보(회원이 만든 경우) — 항목: 키의 해시값, 키 이름, 권한 범위, 만든 · 마지막으로 쓴 · 만료 시각. 목적: 회원의 AI 에이전트가 그 회원의 여행만 다루게 하기. 키는 만든 뒤 최장 90일이 지나면 쓸 수 없습니다.",
            `남용 방지 기록 — 항목: 접속 주소(IP)를 날마다 다른 값으로 바꾼 것과 요청 횟수, 이용자별 요청 횟수. 목적: 요청 한도 지키기와 부정 이용 막기. 기간: 접속 주소 값 ${RETENTION.abuseIpToken[0]}, 이용자별 횟수 ${RETENTION.usageCounts[0]}.`,
            `동의 기록 — 항목: 동의 · 철회한 항목, 약관 버전, 시각, 동의할 때 보여 준 약관 전문의 지문(해시값), 접속 주소를 서버 비밀값으로 바꾼 값, 브라우저 정보(User-Agent). 목적: 언제 무엇에 동의했는지 증명. 기간: ${RETENTION.consentRecords[0]}.`,
          ),
          `여행 정보와 채팅 정보의 보유 기간은 다음과 같습니다. 게스트: ${RETENTION.guestData[0]}. 회원: ${RETENTION.memberData[0]}. 이용자가 여행을 삭제하면 그 여행의 정보는 바로 지워집니다. 다만 처리 기록의 보유 기간은 ${RETENTION.caseRecords[0]}입니다.`,
        ),
        paras(
          "The Operator uses the following information only for the stated purposes and keeps it only for the stated periods.",
          list(
            `Usage state — items: a random user number created by the Service, and the sign-in session cookie (the server stores only a hash of its value). Purpose: keeping the user signed in and confirming that requests come from that user. Period: sessions last ${RETENTION.guestSession[1]} for guests and ${RETENTION.memberSession[1]} for members; the user number is kept as long as the trip information below.`,
            "Trip information — items: the original travel plan (pasted text, and the text and file names read from files and photos; the uploaded files themselves are not stored), the schedule read from it (places, times, party size, budget, booking numbers and anything else written in the plan), answers to the travel preference questions (theme, companions including any description typed in, priorities, indoors or outdoors, what to do when plans go wrong, pace), other trip conditions the user gives, and the schedule change history. Purpose: reading and checking plans, drafting schedules, watching trips and sending alerts, and trip plan links.",
            "Chat information — items: the user's questions, the Service's answers, and the records of how each question was handled (handling records). Purpose: answering questions, applying and undoing schedule changes, and checking for mistakes.",
            "Member information (if a Google account is connected) — items: a value derived from the Google account's unique number using a server secret, and the time of connection. The Google account's email, name and photo are not received. Purpose: member sign-in. Period: until the account is disconnected.",
            "Agent key information (if a member creates one) — items: a hash of the key, the key's name, its permission scope, and when it was created, last used and expires. Purpose: letting a member's AI agent work only on that member's trips. A key stops working at most 90 days after it is created.",
            `Abuse prevention records — items: the connecting address (IP) converted into a value that changes every day, with request counts, and per-user request counts. Purpose: enforcing request limits and preventing misuse. Period: ${RETENTION.abuseIpToken[1]} for the address values and ${RETENTION.usageCounts[1]} for the per-user counts.`,
            `Consent records — items: the item agreed to or withdrawn, the terms version, the time, a fingerprint (hash) of the full terms text shown, the connecting address converted with a server secret, and browser information (User-Agent). Purpose: proving what was agreed and when. Period: ${RETENTION.consentRecords[1]}.`,
          ),
          `Trip and chat information is kept as follows. Guests: ${RETENTION.guestData[1]}. Members: ${RETENTION.memberData[1]}. When a user deletes a trip, that trip's information is deleted at once. Handling records, however, are kept for: ${RETENTION.caseRecords[1]}.`,
        ),
      ],
    },
    {
      heading: ["제3조 (동의를 거부할 권리와 불이익)", "Article 3 (Right to refuse and its effect)"],
      body: [
        "이용자는 이 동의를 거부할 수 있습니다. 다만 제2조의 정보는 서비스를 제공하는 데 꼭 필요하므로, 거부하면 서비스를 이용할 수 없습니다. 선택 동의(민감정보, 개인위치정보, 알림 채널 정보)는 거부해도 서비스를 이용할 수 있습니다.",
        "The user may refuse this consent. However, the information in Article 2 is necessary to provide the Service, so a user who refuses cannot use the Service. The optional consents (sensitive data, personal location data, alert channel data) may be refused without losing access to the Service.",
      ],
    },
    {
      heading: ["제4조 (파기 절차와 방법)", "Article 4 (How data is destroyed)"],
      body: [
        paras(
          "① 운영자는 보유 기간이 지나거나 처리 목적을 이룬 개인정보를 지체 없이 파기합니다.",
          "② 서비스의 개인정보는 전자 파일(데이터베이스)로만 보관하며, 파기할 때는 데이터베이스에서 지웁니다.",
          "③ 게스트의 자료는 보유 기간이 지나면 자동 정리 작업이 지웁니다. 이용자가 여행 삭제를 누르면 그 여행의 일정 · 계획 원문 · 채팅 · 알림 기록이 바로 지워집니다. 처리 기록은 제2조에 적힌 기간에 따릅니다.",
        ),
        paras(
          "(1) The Operator destroys personal data without delay once its retention period has passed or its purpose has been achieved.",
          "(2) The Service keeps personal data only as electronic files (in a database) and destroys it by deleting it from the database.",
          "(3) Guests' data is deleted by an automatic clean-up job when its retention period ends. When a user deletes a trip, that trip's schedule, original plan, chat and alert records are deleted at once. Handling records follow the period stated in Article 2.",
        ),
      ],
    },
    {
      heading: ["제5조 (제3자 제공)", "Article 5 (Disclosure to third parties)"],
      body: [
        paras(
          "① 운영자는 이용자의 개인정보를 제3자에게 제공하지 않습니다. 다만 법령에 따라 제공해야 하는 경우는 예외입니다.",
          "② 다음은 이용자가 직접 정한 곳으로 이용자의 지시에 따라 보내는 것입니다.",
          list(
            "이용자가 에이전트 키로 연결한 AI 서비스가 그 이용자의 여행을 읽는 경우 — 그 AI 서비스의 처리방침이 적용됩니다.",
            "이용자가 연결한 메신저로 알림을 보내는 경우 — 「알림 채널 정보 수집 · 이용 동의」가 정합니다.",
            "이용자가 여행계획서 링크를 다른 사람에게 보내는 경우 — 링크를 가진 사람은 누구나 그 여행의 일정을 볼 수 있습니다.",
          ),
          "③ 여행계획서 링크는 로그인 없이 열리므로, 이용자가 여행 계획이나 일정 변경 요청에 적은 내용(종교 · 건강 같은 민감정보를 적었다면 그 내용 포함)이 링크를 가진 사람에게 보일 수 있습니다. 공개하지 않으려면 링크를 공유하지 마십시오. 링크에는 만료 기한이 없어, 이미 공유한 링크를 막으려면 그 여행을 삭제해야 합니다.",
        ),
        paras(
          "(1) The Operator does not disclose users' personal data to third parties, except where the law requires it.",
          "(2) The following are transfers to places the user has chosen, made on the user's instructions:",
          list(
            "an AI service the user connected with an agent key reading that user's trips — that AI service's privacy policy applies;",
            "alerts sent to the messenger the user connected — governed by the \"Consent to Collection and Use of Alert Channel Data\";",
            "the user sending a trip plan link to someone — anyone who has the link can see that trip's schedule.",
          ),
          "(3) Because the trip plan link opens without signing in, what the user wrote in the travel plan or in schedule change requests (including any sensitive data such as religion or health, if written) may be visible to anyone who has the link. To keep it private, do not share the link. The link does not expire, so to block a link that has already been shared the user must delete the trip.",
        ),
      ],
    },
    {
      heading: ["제6조 (처리 위탁과 국외 이전)", "Article 6 (Outsourcing and transfers abroad)"],
      body: [
        paras(
          "① 운영자는 서비스를 제공하기 위해 다음 업체에 개인정보 처리를 맡깁니다. 이 업체는 국외에 있습니다.",
          list(
            "받는 자: Cloudflare, Inc.(미국) — 연락처 dpo@cloudflare.com",
            "맡기는 일: 서비스 접속 경로의 보호와 전달(서비스로 오는 모든 웹 접속이 이 업체의 망을 거칩니다), 사람인지 확인하는 절차(Turnstile)",
            "이전되는 항목: 접속 주소(IP), 브라우저 정보, 접속하는 동안 오가는 요청 내용, 사람 확인 값",
            "이전 시기와 방법: 이용자가 서비스에 접속할 때마다 네트워크를 통해 전송",
            "받는 자의 보유 기간: 그 업체의 처리방침에 따름",
            "거부 방법과 효과: 모든 접속이 이 업체를 거치므로, 이전을 거부하면 서비스를 이용할 수 없습니다.",
          ),
          "② 다음 외부 조회에는 이용자를 알아볼 수 있는 정보(이용자 번호, 접속 주소, 이름)를 보내지 않고, 장소 이름 · 좌표 · 검색어만 보냅니다.",
          list(
            "카카오(장소 이름으로 장소 찾기, 장소 검색) — 일정 항목의 이름과 이용자가 입력한 검색어",
            "Google Places(식당 운영 여부 확인) — 일정에 있는 식당 이름과 좌표",
            "한국관광공사 · 국가유산청(관광 정보 · 좌표 확인) — 장소 이름",
            "Open-Meteo · 기상청(날씨) — 일정 장소의 좌표",
          ),
          "③ 여행 계획 읽기 · 일정 짜기 · 채팅 답변에 쓰는 언어 모델은 운영자가 관리하는 서버에서 돌리며, 이 내용을 외부 언어 모델 업체에 보내지 않습니다.",
          "④ 처리를 맡기는 업체나 맡기는 일이 바뀌면 운영자는 이 처리방침을 고쳐 알립니다.",
        ),
        paras(
          "(1) To provide the Service, the Operator outsources the processing of personal data to the following company, which is located abroad.",
          list(
            "Recipient: Cloudflare, Inc. (United States) — contact dpo@cloudflare.com",
            "Work outsourced: protecting and relaying the connection to the Service (every web connection to the Service passes through this company's network), and the check that the user is human (Turnstile)",
            "Items transferred: the connecting address (IP), browser information, the request contents passing through while connected, and the human-check value",
            "When and how: transmitted over the network each time the user connects to the Service",
            "Recipient's retention period: as set by that company's privacy policy",
            "How to refuse and the effect: every connection passes through this company, so a user who refuses the transfer cannot use the Service.",
          ),
          "(2) The following outside lookups do not send information that identifies the user (user number, connecting address, name); they send only place names, coordinates and search words.",
          list(
            "Kakao (finding places by name, place search) — schedule item names and search words typed by the user",
            "Google Places (checking whether restaurants are open) — names and coordinates of restaurants in the schedule",
            "Korea Tourism Organization and Korea Heritage Service (tourism information and coordinates) — place names",
            "Open-Meteo and the Korea Meteorological Administration (weather) — coordinates of places in the schedule",
          ),
          "(3) The language models used to read travel plans, draft schedules and answer chat run on servers the Operator manages; this content is not sent to outside language model providers.",
          "(4) If the outsourced companies or the work outsourced change, the Operator will update and announce this policy.",
        ),
      ],
    },
    {
      heading: ["제7조 (이용자의 권리와 행사 방법)", "Article 7 (Users' rights and how to use them)"],
      body: [
        paras(
          "① 이용자는 언제든 자기 개인정보의 열람, 정정, 삭제, 처리정지를 요구할 수 있고, 동의를 철회할 수 있습니다.",
          "② 다음은 서비스 화면에서 직접 할 수 있습니다.",
          list(
            "여행 삭제(바로 지워짐), 일정 수정, 계획서 내려받기",
            "선택 동의의 철회(마이페이지)",
            "소셜 계정 연결 해제, 에이전트 키 폐기, 디스코드 웹훅 삭제",
          ),
          `③ 화면에서 할 수 없는 요구(회원 자료 전체의 삭제, 처리 기록의 열람 · 삭제 등)는 문의처(${OPERATOR.contact})로 할 수 있습니다. 운영자는 관계 법령이 정한 기간 안에 처리하고 결과를 알려야 합니다.`,
          "④ 게스트는 브라우저를 닫으면 로그인 상태가 끝나고, 그 뒤에는 운영자가 요청한 사람이 그 게스트 본인인지 확인할 방법이 없습니다. 그래서 게스트의 화면 밖 요구는 처리하기 어려울 수 있습니다. 게스트의 자료는 제2조의 기간이 지나면 자동으로 지워집니다.",
          "⑤ 이용자는 필수 동의도 철회할 수 있으며, 그러면 서비스를 이용할 수 없게 됩니다.",
        ),
        paras(
          "(1) The user may at any time ask to see, correct, delete or stop the processing of their personal data, and may withdraw consent.",
          "(2) The following can be done directly on the Service screens:",
          list(
            "deleting a trip (deleted at once), editing the schedule, downloading the plan;",
            "withdrawing optional consents (My Page);",
            "disconnecting a social account, revoking an agent key, deleting the Discord webhook.",
          ),
          `(3) Requests that cannot be made on screen (deleting all of a member's data, seeing or deleting handling records, and so on) may be sent to ${OPERATOR.contact}. The Operator must handle them within the period set by law and report the result.`,
          "(4) A guest's signed-in state ends when the browser is closed, after which the Operator has no way to confirm that a person making a request is that guest. Off-screen requests from guests may therefore be difficult to handle. Guests' data is deleted automatically when the period in Article 2 ends.",
          "(5) The user may also withdraw a required consent, after which the user can no longer use the Service.",
        ),
      ],
    },
    {
      heading: ["제8조 (자동화된 판단)", "Article 8 (Automated decisions)"],
      body: [
        "서비스는 사람의 개입 없이, 일정에 문제가 생겼을 때 일정을 바꿀지 · 무엇으로 바꿀지 · 먼저 물을지를 자동으로 판단합니다(「triPilot 서비스 이용약관」 제6조(일정 변경과 되돌리기)). 이용자는 그 판단의 이유를 물을 수 있고, 반영된 변경을 되돌리거나 다른 안을 요청할 수 있습니다.",
        "The Service decides automatically, without human involvement, whether to change the schedule when a problem arises, what to change it to, and whether to ask first (Article 6, Schedule changes and undoing them, of the \"triPilot Terms of Service\"). The user may ask for the reasons for a decision, and may undo an applied change or ask for another option.",
      ],
    },
    {
      heading: ["제9조 (안전성 확보 조치)", "Article 9 (Security measures)"],
      body: [
        paras(
          "운영자는 개인정보를 지키기 위해 다음 조치를 합니다.",
          list(
            "로그인 세션 값, 사용자 키, 에이전트 키는 원래 값 대신 해시값으로만 저장합니다.",
            "구글 계정 고유 번호와 접속 주소는 서버 비밀값으로 바꾼 값으로만 저장합니다.",
            "디스코드 웹훅 주소는 암호화해 저장하고, 원래 주소를 화면 · 응답 · 로그에 내보내지 않습니다.",
            "세션 쿠키는 화면의 스크립트가 읽을 수 없게 하고, 보안 연결(https)에서만 보내며, 다른 사이트가 이용자 대신 요청을 보내지 못하게 확인합니다.",
            "채팅 기록을 저장할 때 전화번호 · 카드 번호 · 이메일 앞부분 같은 일부 형식은 가립니다.",
            "운영자 관리 화면은 비밀번호로 로그인한 사람만 쓸 수 있습니다.",
            "요청 횟수를 제한하고, 필요하면 사람인지 확인합니다.",
          ),
          "여행 계획과 채팅 내용 자체는 별도로 암호화하지 않고 데이터베이스에 저장합니다.",
        ),
        paras(
          "The Operator takes the following measures to protect personal data.",
          list(
            "Sign-in session values, user keys and agent keys are stored only as hashes, not their original values.",
            "Google account unique numbers and connecting addresses are stored only as values converted with a server secret.",
            "Discord webhook addresses are stored encrypted, and the original address is not exposed on screens, in responses or in logs.",
            "The session cookie cannot be read by scripts on the page, is sent only over secure (https) connections, and is checked so that other sites cannot send requests on the user's behalf.",
            "When chat history is stored, some formats such as phone numbers, card numbers and the first part of email addresses are hidden.",
            "Only people who sign in with a password can use the Operator's admin screens.",
            "Request counts are limited and, where needed, users are asked to show they are human.",
          ),
          "Travel plans and chat contents themselves are stored in the database without separate encryption.",
        ),
      ],
    },
    {
      heading: ["제10조 (쿠키와 브라우저 저장소)", "Article 10 (Cookies and browser storage)"],
      body: [
        paras(
          "① 서비스는 로그인 상태를 지키는 세션 쿠키 하나만 씁니다. 광고 · 분석용 쿠키는 쓰지 않습니다. 게스트의 쿠키는 브라우저를 닫으면 지워지고, 회원의 쿠키는 최장 30일 유지됩니다.",
          "② 서비스는 이용자의 브라우저 저장소에 다음을 둡니다. 이 정보는 이용자의 기기에만 있고, 여행 취향 설문 답은 여행을 등록하거나 일정을 짜 달라고 할 때 서버로 보냅니다.",
          list(
            "오래 남는 저장소: 화면 설정(언어 · 테마 등), 처음 사용 안내의 진행 상태와 여행 취향 설문 답(직접 적은 동행 설명 포함), 동의 상태 사본",
            "탭을 닫으면 지워지는 저장소: 최근 채팅 60개, 작성 중인 여행 계획 글, 소셜 로그인 진행 값",
          ),
          "③ 이용자는 브라우저 설정에서 쿠키를 막거나 사이트 데이터를 지울 수 있습니다. 쿠키를 막으면 로그인 상태를 유지할 수 없어 서비스를 이용할 수 없습니다.",
          "④ 다음은 이용자의 브라우저가 외부 업체에 직접 연결해 받아 오는 것이며, 그 업체는 이용자의 접속 주소와 브라우저 정보를 받습니다: 지도 그림(OpenStreetMap, 운영 설정에 따라 구글 지도), 사람 확인 화면(Cloudflare Turnstile), 한국관광공사의 장소 사진.",
        ),
        paras(
          "(1) The Service uses only one cookie, the session cookie that keeps the user signed in. It does not use advertising or analytics cookies. A guest's cookie is deleted when the browser is closed; a member's cookie lasts at most 30 days.",
          "(2) The Service keeps the following in the user's browser storage. This stays on the user's device; the travel preference answers are sent to the server when the user registers a trip or asks for a schedule to be drafted.",
          list(
            "Long-lived storage: display settings (language, theme and so on), progress through the first-use guide and the travel preference answers (including any companion description typed in), and a copy of the consent state",
            "Storage cleared when the tab is closed: the last 60 chat messages, a travel plan being written, and social sign-in progress values",
          ),
          "(3) The user may block cookies or clear site data in the browser settings. If cookies are blocked, the signed-in state cannot be kept and the Service cannot be used.",
          "(4) The user's browser connects directly to the following outside providers, which receive the user's connecting address and browser information: map images (OpenStreetMap, or Google Maps depending on the operating settings), the human-check screen (Cloudflare Turnstile), and place photos from the Korea Tourism Organization.",
        ),
      ],
    },
    {
      heading: ["제11조 (만 14세 미만 아동)", "Article 11 (Children under 14)"],
      body: [
        "서비스는 만 14세 미만 아동이 이용할 수 없으며(「triPilot 서비스 이용약관」 제7조), 운영자는 만 14세 미만 아동의 개인정보를 알고서 수집하지 않습니다.",
        "Children under 14 may not use the Service (Article 7 of the \"triPilot Terms of Service\"), and the Operator does not knowingly collect personal data of children under 14.",
      ],
    },
    {
      heading: ["제12조 (개인정보 보호책임자와 문의)", "Article 12 (Privacy officer and contact)"],
      body: [
        paras(
          list(
            `개인정보 보호책임자: ${OPERATOR.privacyOfficer}`,
            `문의: ${OPERATOR.contact}`,
          ),
          "이용자는 개인정보에 관한 문의, 불만 처리, 피해 구제를 보호책임자에게 요청할 수 있습니다.",
        ),
        paras(
          list(
            `Privacy officer: ${OPERATOR.privacyOfficer}`,
            `Contact: ${OPERATOR.contact}`,
          ),
          "The user may contact the privacy officer with questions, complaints or requests for remedy about personal data.",
        ),
      ],
    },
    {
      heading: ["제13조 (권익 침해에 대한 구제)", "Article 13 (Remedies)"],
      body: [
        "이용자는 개인정보 침해에 대해 개인정보분쟁조정위원회, 한국인터넷진흥원 개인정보침해신고센터, 대검찰청, 경찰청에 분쟁 조정이나 상담 · 신고를 신청할 수 있습니다.",
        "For infringements of personal data, the user may apply for dispute mediation, advice or reporting to the Personal Information Dispute Mediation Committee, the Korea Internet & Security Agency's Personal Information Infringement Report Center, the Supreme Prosecutors' Office or the Korean National Police Agency.",
      ],
    },
    {
      heading: ["제14조 (처리방침의 변경)", "Article 14 (Changes to this policy)"],
      body: [
        `이 처리방침은 ${TERMS_EFFECTIVE}부터 적용됩니다(약관 버전 ${TERMS_VERSION}). 내용이 바뀌면 운영자는 「triPilot 서비스 이용약관」 제3조(약관의 게시와 변경)와 같은 방법으로 알리고, 이용자의 동의를 다시 받습니다.`,
        `This policy applies from ${TERMS_EFFECTIVE} (terms version ${TERMS_VERSION}). If it changes, the Operator announces the change in the same way as Article 3 (Posting and changing these terms) of the "triPilot Terms of Service" and asks users to agree again.`,
      ],
    },
    LANGUAGE_SECTION,
  ],
};

const sensitive: TermsDoc = {
  code: "sensitive",
  required: false,
  title: ["민감정보 수집 · 이용 동의 (선택)", "Consent to Collection and Use of Sensitive Data (optional)"],
  summary: [
    "종교와 관련된 식사 조건(예: 할랄)처럼 민감할 수 있는 정보를 일정 확인에 반영하려면 이 동의가 필요합니다. 동의하지 않아도 서비스를 이용할 수 있으며, 그 조건만 반영되지 않습니다.",
    "This consent is needed to take possibly sensitive information, such as religion-related food conditions (for example halal), into account when checking your schedule. You can use the Service without it; only those conditions are not taken into account.",
  ],
  sections: [
    {
      heading: ["제1조 (이 동의가 다루는 정보)", "Article 1 (What this consent covers)"],
      body: [
        paras(
          "이 동의는 개인정보 보호법이 민감정보로 정한 정보 가운데 서비스가 받을 수 있는 다음 정보에 적용됩니다.",
          list(
            "종교 등 신념과 관련된 식사 조건(예: 할랄 음식만 먹음, 채식)",
            "여행 취향 설문의 음식 관련 답",
            "이용자가 여행 계획이나 채팅에 직접 적은 종교 · 건강에 관한 내용",
          ),
          "지금 웹 화면의 여행 취향 설문은 종교나 식사 제한을 묻지 않습니다. 이 정보는 이용자가 여행을 등록할 때 식사 조건으로 넣거나(에이전트 키로 쓰는 API 포함), 여행 계획 · 채팅에 직접 적을 때 서비스에 들어옵니다.",
        ),
        paras(
          "This consent applies to the following information that the Personal Information Protection Act treats as sensitive data and that the Service may receive:",
          list(
            "food conditions related to religion or other beliefs (for example, halal only, or vegetarian);",
            "answers about food in the travel preference questions;",
            "anything about religion or health that the user writes into a travel plan or chat.",
          ),
          "The travel preference questions on the web screens do not currently ask about religion or food restrictions. This information reaches the Service when the user enters it as a food condition when registering a trip (including through the API with an agent key), or writes it into a travel plan or chat.",
        ),
      ],
    },
    {
      heading: ["제2조 (수집 · 이용 목적)", "Article 2 (Purpose)"],
      body: [
        "서비스는 이 정보를 일정의 식당이 그 조건에 맞는지 확인하고, 식당을 바꿔야 할 때 조건에 맞는 대체 후보를 고르는 데에만 씁니다.",
        "The Service uses this information only to check whether the restaurants in the schedule meet those conditions and, when a restaurant has to be replaced, to choose alternatives that meet them.",
      ],
    },
    {
      heading: ["제3조 (보유 · 이용 기간)", "Article 3 (Retention period)"],
      body: [
        paras(
          "이 정보는 그 정보가 들어 있는 여행 자료와 같은 기간 동안 보관합니다.",
          list(
            `게스트: ${RETENTION.guestData[0]}`,
            `회원: ${RETENTION.memberData[0]}`,
          ),
          "이용자가 이 동의를 철회하면 서비스는 그 이용자의 여행에 저장된 식사 조건과 설문의 음식 관련 답을 지체 없이 지웁니다.",
        ),
        paras(
          "This information is kept for the same period as the trip data it belongs to.",
          list(
            `Guests: ${RETENTION.guestData[1]}`,
            `Members: ${RETENTION.memberData[1]}`,
          ),
          "If the user withdraws this consent, the Service deletes without delay the food conditions and the food-related survey answers stored with that user's trips.",
        ),
      ],
    },
    {
      heading: ["제4조 (글 속에 적힌 정보의 한계)", "Article 4 (Information written in free text)"],
      body: [
        paras(
          "서비스는 여행 계획 원문이나 채팅 문장 속에 섞여 있는 종교 · 건강 정보를 자동으로 골라내 지우지 못합니다. 이 동의를 하지 않은 이용자는 여행 계획과 채팅에 그런 내용을 적지 않아야 합니다.",
          "이미 적은 내용을 지우려면 이용자는 그 여행을 삭제하거나, 「개인정보 수집 · 이용 동의 및 처리방침」의 권리 행사 방법에 따라 삭제를 요청할 수 있습니다.",
        ),
        paras(
          "The Service cannot automatically find and delete religion or health information mixed into the original travel plan or chat messages. A user who has not given this consent must not write such information into travel plans or chat.",
          "To remove something already written, the user may delete that trip or ask for deletion as described under the rights section of the \"Consent to Collection and Use of Personal Data and Privacy Policy\".",
        ),
      ],
    },
    {
      heading: ["제5조 (제3자 제공과 외부 전송)", "Article 5 (Disclosure to third parties)"],
      body: [
        "운영자는 이 정보를 제3자에게 제공하지 않습니다. 식사 조건 값은 운영자의 서버 안에서만 쓰며, 지도 · 장소 조회 업체 등 외부 업체에 보내지 않습니다.",
        "The Operator does not disclose this information to third parties. Food condition values are used only on the Operator's servers and are not sent to outside providers such as map or place lookup services.",
      ],
    },
    {
      heading: ["제6조 (동의를 거부할 권리와 불이익)", "Article 6 (Right to refuse and its effect)"],
      body: [
        "이용자는 이 동의를 거부할 수 있습니다. 거부해도 서비스를 이용할 수 있으며, 식당을 확인하거나 바꿀 때 종교 · 신념과 관련된 식사 조건이 반영되지 않는 것 말고는 불이익이 없습니다. 이용자는 동의한 뒤에도 마이페이지에서 언제든 철회할 수 있습니다.",
        "The user may refuse this consent. The user can still use the Service; the only effect is that food conditions related to religion or beliefs are not taken into account when restaurants are checked or replaced. The user may withdraw this consent at any time on My Page.",
      ],
    },
    LANGUAGE_SECTION,
  ],
};

const location: TermsDoc = {
  code: "location",
  required: false,
  title: ["개인위치정보 수집 · 이용 동의 및 위치기반서비스 이용약관 (선택)", "Consent to Collection and Use of Personal Location Data and Location-Based Service Terms (optional)"],
  summary: [
    "지도에 내 위치를 보여 주고, 여행 중 머문 곳을 확인해 일정이 늦어지는지 살피려면 이 동의가 필요합니다. 위치는 서비스 화면이 열려 있을 때만 읽고, 다른 곳에 제공하지 않습니다. 동의하지 않아도 서비스를 이용할 수 있습니다.",
    "This consent is needed to show your position on the map and to see where you stopped during the trip so the Service can tell whether the schedule is slipping. Your location is read only while the Service screen is open and is not given to anyone else. You can use the Service without it.",
  ],
  sections: [
    {
      heading: ["제1조 (목적)", "Article 1 (Purpose)"],
      body: [
        "이 약관은 운영자가 제공하는 위치기반서비스의 이용 조건과, 운영자가 이용자의 개인위치정보를 수집 · 이용하는 데 필요한 사항을 정합니다. 이 약관에 없는 사항은 「triPilot 서비스 이용약관」과 「개인정보 수집 · 이용 동의 및 처리방침」을 따르며, 말의 뜻도 같습니다.",
        "These terms set out the conditions of the location-based service the Operator provides and what is needed for the Operator to collect and use users' personal location data. Matters not covered here follow the \"triPilot Terms of Service\" and the \"Consent to Collection and Use of Personal Data and Privacy Policy\", and words have the same meanings.",
      ],
    },
    {
      heading: ["제2조 (사업자 정보)", "Article 2 (Business details)"],
      body: [
        list(
          `상호: ${OPERATOR.name}`,
          `대표자: ${OPERATOR.representative}`,
          `주소: ${OPERATOR.address}`,
          `연락처: ${OPERATOR.contact}`,
        ),
        list(
          `Name: ${OPERATOR.name}`,
          `Representative: ${OPERATOR.representative}`,
          `Address: ${OPERATOR.address}`,
          `Contact: ${OPERATOR.contact}`,
        ),
      ],
    },
    {
      heading: ["제3조 (서비스 내용)", "Article 3 (What the location-based service does)"],
      body: [
        paras(
          "운영자는 이용자가 이 약관에 동의한 경우에만 다음 서비스를 제공합니다.",
          list(
            "지도에 내 위치 표시: 여행 화면의 지도에 이용자의 현재 위치를 표시합니다.",
            "머문 곳 확인과 일정 지켜보기: 여행 중 받은 위치로 이용자가 한곳에 머문 곳(머문 지점)을 계산해 일정의 장소와 맞춰 보고, 일정 시작 시각이 지났는데 그 장소에 도착하지 않았거나 일정에 없는 곳에 오래 머무는 경우를 찾아 일정 확인에 씁니다.",
            "내 위치에서 길 · 근처 장소 묻기: 채팅에서 「내 위치 알려 주고 다시 묻기」를 누르면 그 위치를 출발지로 삼아 그 질문에 답합니다.",
          ),
        ),
        paras(
          "The Operator provides the following only if the user has agreed to these terms.",
          list(
            "Showing your position on the map: the user's current position is shown on the trip screen's map.",
            "Seeing where you stopped and watching the schedule: from the positions received during the trip, the Service works out where the user stayed in one place (stops), matches them with the places in the schedule, and uses them to check the schedule — for example when a scheduled start time has passed and the user has not arrived, or when the user stays a long time somewhere not in the schedule.",
            "Asking for directions or nearby places from your position: when the user presses \"Share my location and ask again\" in chat, the Service answers that question using the position as the starting point.",
          ),
        ),
      ],
    },
    {
      heading: ["제4조 (수집 항목과 방법)", "Article 4 (What is collected and how)"],
      body: [
        paras(
          "① 수집 항목: 위도, 경도, 정확도(오차 반경), 위치를 잰 시각, 그 위치가 속한 여행, 이용자 번호. 기기 이름과 접속 주소 원문은 위치와 함께 저장하지 않습니다.",
          "② 수집 방법: 이용자 브라우저의 위치 기능으로 읽습니다. 이 동의와 브라우저(기기)의 위치 권한이 모두 있어야 읽습니다.",
          "③ 서비스는 서비스 화면이 열려 있을 때만 위치를 읽습니다. 화면을 닫았거나 다른 앱을 쓰는 동안에는 읽지 않으며, 그동안의 위치를 짐작해 채우지 않습니다. 그래서 머문 곳 확인은 화면을 켜 둔 동안의 위치로만 합니다.",
        ),
        paras(
          "(1) Items collected: latitude, longitude, accuracy (error radius), the time the position was measured, the trip the position belongs to, and the user number. The device name and the original connecting address are not stored with positions.",
          "(2) How: positions are read through the user's browser location feature. Both this consent and the browser's (device's) location permission are required.",
          "(3) The Service reads positions only while the Service screen is open. It does not read them while the screen is closed or another app is in use, and does not guess positions for that time. Stops are therefore worked out only from positions taken while the screen was on.",
        ),
      ],
    },
    {
      heading: ["제5조 (이용 목적과 보유 기간)", "Article 5 (Purpose and retention)"],
      body: [
        paras(
          "① 운영자는 개인위치정보를 제3조(서비스 내용)의 서비스를 제공하는 데에만 씁니다.",
          "② 채팅의 「내 위치 알려 주고 다시 묻기」로 받은 위치는 그 질문에 답하는 데에만 쓰고, 답한 뒤 저장하지 않습니다.",
          `③ 머문 곳 확인을 위해 서버에 보낸 위치 점과 계산한 머문 지점의 보유 기간은 ${RETENTION.locationPoints[0]}이며, 기간이 지나면 즉시 파기합니다. 이용자가 그 여행을 삭제하면 그 여행의 위치 정보도 바로 지웁니다.`,
        ),
        paras(
          "(1) The Operator uses personal location data only to provide the services in Article 3 (What the location-based service does).",
          "(2) A position received through \"Share my location and ask again\" in chat is used only to answer that question and is not stored after answering.",
          `(3) Positions sent to the server for working out stops, and the stops calculated from them, are kept for: ${RETENTION.locationPoints[1]}, and are destroyed at once when that period ends. If the user deletes the trip, its location data is deleted at once as well.`,
        ),
      ],
    },
    {
      heading: ["제6조 (위치정보 이용 · 제공사실 확인자료)", "Article 6 (Records of the use and provision of location data)"],
      body: [
        paras(
          "① 운영자는 개인위치정보를 수집 · 이용 · 제공한 사실(누구의 위치를, 언제, 어떤 목적으로)을 위치정보시스템에 자동으로 기록하고 보존합니다.",
          `② 보유 근거는 「위치정보의 보호 및 이용 등에 관한 법률」이고, 보유 기간은 ${RETENTION.locationFactLog[0]}입니다.`,
          "③ 이용자는 자기에 대한 확인자료의 열람이나 고지를 요구할 수 있습니다.",
        ),
        paras(
          "(1) The Operator automatically records and keeps in its location information system the fact that personal location data was collected, used or provided (whose position, when, and for what purpose).",
          `(2) The legal basis for keeping these records is the Act on the Protection, Use, etc. of Location Information, and they are kept for: ${RETENTION.locationFactLog[1]}.`,
          "(3) The user may ask to see these records about themselves or to be told what they contain.",
        ),
      ],
    },
    {
      heading: ["제7조 (제3자 제공과 통보)", "Article 7 (Disclosure to third parties and notification)"],
      body: [
        paras(
          "① 운영자는 개인위치정보를 제3자에게 제공하지 않습니다. 이용자의 위치 좌표를 지도 · 길찾기 · 날씨 업체 같은 외부 업체에 보내지도 않습니다.",
          "② 다만 지도 화면은 이용자의 브라우저가 지도 제공자(OpenStreetMap 등)에게서 화면에 보이는 지역의 지도 그림을 직접 받아 오므로, 지도 제공자는 어느 지역의 지도가 요청됐는지와 이용자의 접속 주소를 알 수 있습니다.",
          "③ 운영자가 앞으로 개인위치정보를 제3자에게 제공하려면 받는 자와 목적을 미리 알리고 따로 동의를 받아야 하며, 제공할 때마다 받는 자 · 제공 일시 · 목적을 이용자에게 바로 알려야 합니다.",
        ),
        paras(
          "(1) The Operator does not disclose personal location data to third parties. It does not send the user's coordinates to outside providers such as map, routing or weather services either.",
          "(2) However, for the map screen the user's browser fetches the map images for the visible area directly from the map provider (OpenStreetMap or others), so the map provider can know which area's map was requested and the user's connecting address.",
          "(3) If the Operator ever wants to provide personal location data to a third party, it must first tell the user the recipient and purpose and obtain separate consent, and must tell the user the recipient, date and time, and purpose each time it provides the data.",
        ),
      ],
    },
    {
      heading: ["제8조 (이용자의 권리와 행사 방법)", "Article 8 (Users' rights and how to use them)"],
      body: [
        paras(
          "① 이용자는 언제든 이 동의의 전부 또는 일부를 철회할 수 있습니다. 마이페이지에서 위치 동의를 끄면 됩니다.",
          "② 이용자는 언제든 위치 수집 · 이용의 일시 중지를 요구할 수 있습니다. 브라우저(기기) 설정에서 이 사이트의 위치 권한을 끄면 그때부터 위치를 읽지 않습니다.",
          `③ 이용자는 자기에 대한 확인자료와 개인위치정보를 제3자에게 제공한 이유 · 내용의 열람이나 고지를 요구할 수 있고, 오류가 있으면 정정을 요구할 수 있습니다. 이 요구는 ${OPERATOR.contact}로 합니다.`,
          "④ 운영자는 이 요구를 거절하지 않으며, 지체 없이 처리해야 합니다.",
        ),
        paras(
          "(1) The user may withdraw all or part of this consent at any time by turning off the location consent on My Page.",
          "(2) The user may at any time ask for the collection and use of their position to be paused. Turning off this site's location permission in the browser (device) settings stops the Service from reading the position from then on.",
          `(3) The user may ask to see, or be told about, the records about themselves and the reasons for and contents of any provision of their personal location data to third parties, and may ask for errors to be corrected. These requests go to ${OPERATOR.contact}.`,
          "(4) The Operator does not refuse these requests and must handle them without delay.",
        ),
      ],
    },
    {
      heading: ["제9조 (동의 철회의 효과)", "Article 9 (What happens when consent is withdrawn)"],
      body: [
        "이용자가 동의를 철회하면 운영자는 위치 수집을 바로 멈추고, 수집한 위치 점 · 머문 지점과 위치정보 이용 · 제공사실 확인자료를 지체 없이 파기합니다. 일부만 철회하면 철회한 부분만 파기합니다.",
        "If the user withdraws consent, the Operator stops collecting positions at once and destroys without delay the positions and stops collected and the records of use and provision of location data. If only part of the consent is withdrawn, only that part is destroyed.",
      ],
    },
    {
      heading: ["제10조 (만 14세 미만 아동)", "Article 10 (Children under 14)"],
      body: [
        "만 14세 미만은 서비스를 이용할 수 없으므로(「triPilot 서비스 이용약관」 제7조), 운영자는 만 14세 미만 아동의 개인위치정보를 수집하지 않으며 법정대리인이나 보호의무자의 동의로 위치정보를 처리하지 않습니다.",
        "Because people under 14 may not use the Service (Article 7 of the \"triPilot Terms of Service\"), the Operator does not collect personal location data of children under 14 and does not process location data on the consent of a legal representative or guardian.",
      ],
    },
    {
      heading: ["제11조 (위치정보 관리책임자)", "Article 11 (Location information manager)"],
      body: [
        `운영자는 개인위치정보를 보호하고 이용자의 불만을 처리하기 위해 위치정보 관리책임자를 둡니다. 위치정보 관리책임자: ${OPERATOR.locationOfficer}`,
        `The Operator appoints a location information manager to protect personal location data and handle users' complaints. Location information manager: ${OPERATOR.locationOfficer}`,
      ],
    },
    {
      heading: ["제12조 (손해배상과 분쟁 조정)", "Article 12 (Compensation and dispute resolution)"],
      body: [
        "운영자가 위치정보 관련 법령을 어겨 이용자에게 손해를 끼치면 관계 법령에 따라 배상합니다. 이용자는 위치정보에 관한 분쟁에 대해 관계 법령에 따른 분쟁 조정 기관에 조정을 신청할 수 있습니다.",
        "If the Operator breaks the laws on location information and causes the user damage, it compensates the user under applicable law. For disputes about location data, the user may apply for mediation to the dispute mediation bodies set by law.",
      ],
    },
    {
      heading: ["제13조 (약관의 변경)", "Article 13 (Changes to these terms)"],
      body: [
        `이 약관은 ${TERMS_EFFECTIVE}부터 적용됩니다(약관 버전 ${TERMS_VERSION}). 이 약관을 바꿀 때는 「triPilot 서비스 이용약관」 제3조(약관의 게시와 변경)를 따르며, 바뀐 뒤에는 다시 동의한 이용자의 위치만 읽습니다.`,
        `These terms apply from ${TERMS_EFFECTIVE} (terms version ${TERMS_VERSION}). Changes follow Article 3 (Posting and changing these terms) of the "triPilot Terms of Service", and after a change the Service reads positions only of users who have agreed again.`,
      ],
    },
    LANGUAGE_SECTION,
  ],
};

const alertChannel: TermsDoc = {
  code: "alert_channel",
  required: false,
  title: ["알림 채널 정보 수집 · 이용 동의 (선택)", "Consent to Collection and Use of Alert Channel Data (optional)"],
  summary: [
    "일정이 바뀐 소식을 디스코드 같은 메신저로 받으려면 그 메신저의 연결 정보를 저장해야 합니다. 동의하지 않아도 서비스를 이용할 수 있고, 최신 일정은 웹과 여행계획서 링크에서 볼 수 있습니다.",
    "To receive schedule-change alerts in a messenger such as Discord, the Service must store that messenger's connection details. You can use the Service without this consent, and the latest schedule is always on the web and the trip plan link.",
  ],
  sections: [
    {
      heading: ["제1조 (수집 · 이용 목적)", "Article 1 (Purpose)"],
      body: [
        "서비스는 이 정보를 이용자가 연결한 메신저로 여행 알림(일정 변경 등)과 연결 확인용 시험 메시지를 보내는 데에만 씁니다.",
        "The Service uses this information only to send trip alerts (such as schedule changes) and connection test messages to the messenger the user has connected.",
      ],
    },
    {
      heading: ["제2조 (수집 항목)", "Article 2 (What is collected)"],
      body: [
        paras(
          list(
            "디스코드: 이용자가 직접 넣거나 「디스코드로 연결」로 만든 웹훅 주소, 화면에 보여 줄 가린 주소 일부, 시험 결과와 그 시각",
            "텔레그램(서비스가 제공하는 경우): 대화 번호, 연결 시각, 연결 상태. 텔레그램 이름 · 사용자명 · 전화번호 · 프로필 사진은 받더라도 저장하지 않습니다.",
            "알림을 받을 곳(어느 메신저인지)",
          ),
          "알림은 한 번에 한 곳으로만 보냅니다. 여러 메신저를 연결했다면 이용자가 마지막에 연결했거나 마이페이지에서 고른 곳으로 보냅니다.",
        ),
        paras(
          list(
            "Discord: the webhook address the user entered or created with \"Connect with Discord\", a partly hidden form of it for display, and the result and time of the last test",
            "Telegram (where the Service offers it): the chat number, the time of connection and the connection status. Telegram names, usernames, phone numbers and profile photos are not stored even if received.",
            "Which messenger alerts go to",
          ),
          "Each alert is sent to one place only. If the user has connected more than one messenger, alerts go to the one connected last or chosen on My Page.",
        ),
      ],
    },
    {
      heading: ["제3조 (보관 방법과 기간)", "Article 3 (How and how long it is kept)"],
      body: [
        paras(
          "웹훅 주소는 암호화해 보관하며, 화면과 응답에는 일부를 가린 모양만 보여 줍니다. 운영자는 웹훅 주소 원문을 로그에 남기지 않습니다.",
          "이 정보는 이용자가 연결을 풀거나 이 동의를 철회할 때까지 보관하고, 그때 지체 없이 지웁니다.",
        ),
        paras(
          "The webhook address is stored encrypted, and screens and responses show only a partly hidden form. The Operator does not write the full webhook address to logs.",
          "This information is kept until the user disconnects the messenger or withdraws this consent, and is then deleted without delay.",
        ),
      ],
    },
    {
      heading: ["제4조 (메신저 업체가 처리하는 정보)", "Article 4 (Information handled by the messenger provider)"],
      body: [
        paras(
          "알림에는 바뀐 일정의 장소 이름 · 시각과 여행계획서 링크가 들어갑니다. 서비스가 보낸 알림은 이용자가 고른 메신저 업체(디스코드 운영사, 텔레그램 운영사)의 서버로 전달되어 그 업체의 정책에 따라 처리 · 보관됩니다.",
          "보낸 알림은 그 메신저에 남으며, 운영자는 보낸 알림을 지우지 않습니다. 알림에 든 여행계획서 링크는 그 채널을 볼 수 있는 사람 누구나 열 수 있으므로, 이용자는 여러 사람이 보는 채널을 연결할 때 이 점을 고려해야 합니다.",
        ),
        paras(
          "Alerts contain the names and times of the changed schedule items and the trip plan link. Alerts the Service sends are delivered to the servers of the messenger provider the user chose (the operator of Discord or of Telegram) and are handled and kept under that provider's policies.",
          "Sent alerts remain in that messenger; the Operator does not delete them. Anyone who can see the channel can open the trip plan link in an alert, so the user must keep this in mind when connecting a channel that several people can see.",
        ),
      ],
    },
    {
      heading: ["제5조 (동의를 거부할 권리와 불이익)", "Article 5 (Right to refuse and its effect)"],
      body: [
        "이용자는 이 동의를 거부할 수 있습니다. 거부해도 서비스를 이용할 수 있으며, 메신저로 알림을 받지 못하는 것 말고는 불이익이 없습니다. 최신 일정은 웹 화면과 여행계획서 링크에서 볼 수 있습니다. 이용자는 마이페이지에서 언제든 연결을 풀거나 이 동의를 철회할 수 있습니다.",
        "The user may refuse this consent. The user can still use the Service; the only effect is that alerts are not sent to a messenger. The latest schedule is shown on the web screens and the trip plan link. The user may disconnect a messenger or withdraw this consent at any time on My Page.",
      ],
    },
    LANGUAGE_SECTION,
  ],
};

/** 순서 = 동의 화면에 보이는 순서(`CONSENT_CODES` 와 같다). */
export const TERMS_DOCS: readonly TermsDoc[] = [serviceTerms, privacy, sensitive, location, alertChannel];
