# KoREC(Korean-Referring-Expression-Coreference)
지칭 표현 온톨로지 주입을 통한 LLM 기반 한국 근대소설 상호참조 해소 향상

---

## Overview

본 프로젝트는 한국 근대소설의 상호참조 해소(coreference resolution) 연구를 위한 세 가지 자원을 제공한다.

| 층위 | 파일 | 역할 |
|------|------|------|
| **온톨로지 스키마** | `ontology_schema.xsd` | 지칭어 온톨로지의 구조를 정의하는 XSD 스키마 |
| **온톨로지 인스턴스** | `coreference_ontology.xml` | 스키마를 따르는 실제 지칭어 데이터 (7개 범주, 62개 entry) |
| **평가 스크립트** | `evaluate_coref.py` | TEI/XML 기반 span-based CoNLL-F1 평가기 |
| **골드 스탠다드** | `data/` | 수동 태깅된 TEI/XML 골드 스탠다드 데이터 |

---

## 1. 온톨로지 스키마 (`ontology_schema.xsd`)

한국 근대문학 인물 지칭 표현의 분류 체계를 XML Schema Definition(XSD)으로 정의한다.

### 구조

```
taxonomy
 └─ category (최상위 7개 범주)
      └─ category (하위 범주)
           └─ entry (개별 지칭 표현)
                ├─ form        표층 형식 (예: "이놈")
                ├─ property    속성 집합
                ├─ contextRule 맥락 의존 규칙 (0개 이상)
                ├─ relation    다른 entry와의 관계 (0개 이상)
                └─ example     용례 (0개 이상)
```

### 속성(property) 체계

각 entry는 다음 속성을 가진다.

| 속성 | 값 | 필수 |
|------|------|------|
| `formality` | `formal` · `neutral` · `informal` · `vulgar` | ✅ |
| `polarity` | `positive` · `neutral` · `negative` · `ambivalent` | ✅ |
| `ambiguity` | `fixed` · `context-dependent` | ✅ |
| `animacy` | `animate` · `deceased` · `objectified` | |
| `dialect` | `standard` · `pyeongan` · `gyeongsang` · `other` | |
| `gender` | `masculine` · `feminine` · `unspecified` | |

### 관계(relation) 타입

| 타입 | 의미 | 예시 |
|------|------|------|
| `standardForm` | 방언 ↔ 표준어 대응 | 님자 → 임자 |
| `intensifiesTo/From` | 비하 강도 계열 | 이년 → 오라질 년 |
| `antonym` | 의미적 대립 | 산 사람 ↔ 죽은 이 |
| `contrastPair` | 서사적 대비 쌍 | 뚱뚱보 ↔ 말라깽이 |

### 네임스페이스

```
http://dh.aks.ac.kr/ontology/referring-expression
```

---

## 2. 온톨로지 인스턴스 (`coreference_ontology.xml`)

스키마를 따르는 실제 지칭어 데이터. 현진건 「운수 좋은 날」과 김동인 「감자」에서 추출한 표현들을 등록하였다.

### 7개 범주 체계

**기존 연구 기반 (4개):**

| # | 범주 | ID | 하위 범주 |
|---|------|----|----------|
| 1 | 대명사 | `pronoun` | 1인칭, 2인칭, 3인칭, 재귀, 지시 |
| 2 | 친족 호칭 | `kinship` | 배우자, 부모, 자녀, 인척, 의사친족 |
| 3 | 사회적 호칭 | `social` | 직업·직함, 신분·지위, 관계적 역할, 나이·성별, 소유·소속 |
| 4 | 대화 호격 | `address` | 친밀·하대, 중립, 존대, 방언 |

**본 연구 확장 (3개):**

| # | 범주 | ID | 하위 범주 |
|---|------|----|----------|
| 5 | 묘사적 지칭 | `epithet` | 상태, 행위, 외양, 비유적, 나이·존재론적 |
| 6 | 욕설·비하 | `invective` | 저주형, 비하형, 경시형, 사물화 |
| 7 | 집합 지칭 | `group` | 포괄적 우리, 소유적 우리, 3인칭 복수, 복수 묘사 |

### 세 레이어

온톨로지는 단순 분류 체계(taxonomy)를 넘어 세 가지 레이어를 포함한다.

**① 속성(property)** — 각 지칭 표현의 격식 수준(formality), 감정 극성(polarity), 중의성(ambiguity) 등을 명시.

**② 관계(relation)** — 표현 간 연결. 방언↔표준어 대응, 비하 강도 계열, 의미적 대립, 서사적 대비 쌍.

**③ 맥락 의존 규칙(contextRule)** — 동일 표현이 맥락에 따라 다른 범주로 분류되어야 하는 조건을 명시. 예:

```xml
<!-- "이놈" — 맥락에 따라 친밀한 호격 vs 실제 비하 -->
<contextRule>
  <condition context="relation[@name='friendship'] AND said[@who=speaker]">
    category→address.intimate, polarity→positive (친밀한 욕)
  </condition>
  <condition context="social-hierarchy-above AND polarity-context=anger">
    category→invective.derogatory, polarity→negative (실제 비하)
  </condition>
  <condition context="self-reference">
    category→invective.derogatory, polarity→negative (자기 비하)
  </condition>
</contextRule>
```

### 범주 간 주요 관계 (Cross-category Relations)

- `address` ↔ `invective` 경계: "이놈" — 친밀 vs 비하 (relation + said 맥락으로 판별)
- `social.status` ↔ `address.respectful` 경계: "아씨" — 서술자 묘사 vs 대화 호격 (said[@who] 유무로 판별)
- `kinship` ↔ `kinship.fictive` 판별: "형님" — 실제 친족 vs 의사 친족 (listPerson relation 정보 참조)
- 비하 강도 계열: 이년 → 오라질 년 → 난장 맞을 년
- 대비 쌍: 뚱뚱보 ↔ 말라깽이, 산 사람 ↔ 죽은 이, 끄는 이 ↔ 탄 이

---

## 3. 평가 스크립트 (`evaluate_coref.py`)

TEI/XML 마크업 상태 그대로 coreference resolution 성능을 평가하는 span-based 평가기.

### 기존 CoNLL 포맷과의 차이

기존 coreference 평가의 표준(CoNLL 포맷)은 토큰 단위 평면 구조로, TEI/XML의 중첩 태그, `said who` 속성, 복합 `ref` 등 TEI 고유 정보를 표현할 수 없다. 본 평가 스크립트는 TEI/XML에서 `<persName ref="...">`, `<rs ref="...">` 태그의 span과 ref 속성을 직접 추출하여 클러스터를 구성하고, 문맥 기반 mention 매칭을 수행한다.

### 평가 파이프라인

```
1. XML → mention 추출     character offset + context window(±15자) 추출
2. 문맥 기반 mention 매칭   골드 mention과 시스템 mention을 텍스트+문맥 유사도로 매칭
3. ID 매핑                 시스템이 자체 생성한 ID를 골드 ID로 매핑 (조건 A, C용)
4. 클러스터 구성            ref 속성 기준으로 mention을 클러스터링
5. CoNLL 메트릭 산출        MUC, B³, CEAFϕ4 → CoNLL-F1 = 평균
```

### 메트릭

| 메트릭 | 관점 | 측정 대상 |
|--------|------|----------|
| **MUC** | link-based | mention 간 연결 정확도 |
| **B³** | mention-based | 개별 mention의 클러스터 귀속 정확도 |
| **CEAFϕ4** | entity-based | 클러스터(인물) 단위 매칭 정확도 |
| **CoNLL-F1** | 종합 | (MUC-F1 + B³-F1 + CEAFϕ4-F1) / 3 |

### 사용법

```bash
python evaluate_coref.py
```

스크립트 내부의 `main()` 함수에서 골드 스탠다드 경로와 시스템 출력 경로를 지정한다. 4가지 조건(A/B/C/D)에 대한 Ablation Study 결과를 자동으로 산출한다.

### Ablation Study 조건

| 조건 | 프롬프트 입력 |
|------|-------------|
| A | 원문(텍스트)만 |
| B | 원문 + 캐릭터 데이터 (listPerson/listRelation XML) |
| C | 원문 + 온톨로지 (XSD 스키마) |
| D | 원문 + 캐릭터 데이터 + 온톨로지 |

---

## 4. 골드 스탠다드 데이터 (`data/`)

수동 TEI/XML 태깅에 의한 골드 스탠다드 데이터. 각 텍스트에 대해 `<persName ref="...">` (고유명), `<rs ref="...">` (지칭 표현), `<said who="...">` (대화문)이 태깅되어 있으며, 인물 목록(`listPerson`)과 인물 간 관계(`listRelation`)가 XML로 함께 제공된다.

**현재 포함:**
- 현진건 「운수 좋은 날」 (222 mentions, 10 clusters)


---

## Author

김가연 (Kim, Gayeon)  
한국학중앙연구원 한국학대학원 인문정보학 박사과정  
[eiloppang.com](http://www.eiloppang.com) · [ORCID](https://orcid.org/0009-0005-1231-6939)
