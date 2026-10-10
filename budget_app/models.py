"""
④ 모델 계층 — 데이터가 '어떤 모양'인지 정의합니다.

하는 일 : 거래·반복 규칙·검색 조건·요약 결과의 필드와 타입을 정합니다.
          (자기 데이터에 대한 간단한 판단, 예: "이 거래가 검색 조건에 맞나?" 정도만)
안 하는 일: 파일 읽기/쓰기(storage), 계산 규칙(services), 화면 출력(formatter)
"""

from dataclasses import asdict, dataclass, field

INCOME = "income"
EXPENSE = "expense"
TRANSACTION_TYPES = (INCOME, EXPENSE)


def make_tx_id(number: int) -> str:
    """번호를 거래 id로 바꿉니다. 12 → 'TX-000012'"""
    return f"TX-{number:06d}"


def id_number(item_id: str) -> int:
    """id에서 번호만 꺼냅니다. 'TX-000012' → 12"""
    return int(item_id.split("-")[1])


@dataclass
class Transaction:
    """[요구 4.2] 거래 1건 (수입 또는 지출)."""

    id: str  # 유일한 번호. 예: "TX-000012"
    type: str  # "income"(수입) 또는 "expense"(지출)
    date: str  # "YYYY-MM-DD"
    amount: int  # 양수 (원 단위)
    category: str  # 등록된 카테고리 이름
    memo: str = ""  # 선택
    tags: list[str] = field(default_factory=list)  # 선택. 예: ["meal", "friend"]

    @property
    def month(self) -> str:
        """'2024-01-15' → '2024-01' (월별 요약에 사용)"""
        return self.date[:7]

    def latest_key(self) -> tuple[str, int]:
        """최신순 기준: 날짜가 늦을수록, 같은 날이면 나중에 추가한(id 번호가 큰) 것이 최신."""
        return (self.date, id_number(self.id))

    def to_dict(self) -> dict:
        """파일에 저장하기 위해 dict로 바꿉니다."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        """파일에서 읽은 dict를 Transaction으로 바꿉니다."""
        return cls(
            id=data["id"],
            type=data["type"],
            date=data["date"],
            amount=data["amount"],
            category=data["category"],
            memo=data.get("memo", ""),
            tags=data.get("tags", []),
        )


@dataclass
class RecurringRule:
    """[보너스] 반복 내역 규칙. 예: 매월 25일 월급(income) 3000000원."""

    id: str  # 예: "RC-001"
    type: str
    day: int  # 매월 며칠 (1~31)
    amount: int
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)
    applied_months: list[str] = field(default_factory=list)  # 이미 거래를 만든 달 (중복 방지)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringRule":
        return cls(
            id=data["id"],
            type=data["type"],
            day=data["day"],
            amount=data["amount"],
            category=data["category"],
            memo=data.get("memo", ""),
            tags=data.get("tags", []),
            applied_months=data.get("applied_months", []),
        )


@dataclass
class SearchFilter:
    """[요구 4.8] 검색 조건 묶음. 값이 None인 조건은 검사하지 않습니다."""

    date_from: str | None = None  # --from (이 날짜 포함 이후)
    date_to: str | None = None  # --to (이 날짜 포함 이전)
    month: str | None = None  # --month (export에서 사용)
    category: str | None = None  # --category
    type: str | None = None  # --type
    keyword: str | None = None  # --q (메모에 들어 있는 단어)
    tag: str | None = None  # --tag

    def matches(self, tx: Transaction) -> bool:
        """거래 1건이 모든 조건을 만족하면 True.

        날짜는 'YYYY-MM-DD' 글자 그대로 비교해도 순서가 맞습니다. ('2024-01-05' < '2024-01-15')
        """
        if self.date_from and tx.date < self.date_from:
            return False
        if self.date_to and tx.date > self.date_to:
            return False
        if self.month and tx.month != self.month:
            return False
        if self.category and tx.category != self.category:
            return False
        if self.type and tx.type != self.type:
            return False
        if self.keyword and self.keyword.lower() not in tx.memo.lower():
            return False
        if self.tag and self.tag not in tx.tags:
            return False
        return True


@dataclass
class MonthlySummary:
    """[요구 4.9, 4.10] 월별 요약 결과. (계산은 services, 출력은 formatter가 합니다)"""

    month: str
    count: int  # 그 달의 거래 건수 (0이면 '데이터 없음')
    total_income: int
    total_expense: int
    top_expenses: list[tuple[str, int]]  # 지출 TOP N. 예: [("rent", 150000), ("food", 45000)]
    budget: int | None  # 그 달 예산 (설정하지 않았으면 None)

    @property
    def balance(self) -> int:
        """잔액 = 총수입 - 총지출"""
        return self.total_income - self.total_expense

    @property
    def budget_usage(self) -> float | None:
        """예산 사용률(%). 예산이 없으면 None."""
        if self.budget is None:
            return None
        return self.total_expense / self.budget * 100

    @property
    def over_budget(self) -> int:
        """예산 초과 금액. 초과하지 않았거나 예산이 없으면 0."""
        if self.budget is None:
            return 0
        return max(0, self.total_expense - self.budget)


@dataclass
class ImportResult:
    """[요구 4.12] import 결과: 등록한 건수 + 건너뛴 행과 그 이유."""

    imported: int
    skipped: list[str]  # 예: ["3번째 줄: 금액은 0보다 커야 합니다 (양수)."]
