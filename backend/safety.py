import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ContactBlock:
    reason: str


LEGAL_PATTERNS = (
    r"запрет\w*\s+на\s+регистрационн\w*\s+действ",
    r"(?:автомобиль|машина|авто)\s+(?:в\s+)?залог",
    r"(?:автомобиль|машина|авто)\s+(?:в\s+)?кредит",
    r"действующ\w*\s+кредит",
    r"юридическ\w*\s+обремен",
)

DEALER_BAN_PATTERNS = (
    r"автосалон\w*\s+(?:не\s+)?(?:звонить|не\s+интересуют|не\s+беспокоить)",
    r"\bсалон\w*\s+(?:не\s+)?(?:звонить|не\s+интересуют|не\s+беспокоить)",
    r"не\s+(?:звонить|писать|беспокоить)\s+(?:из\s+)?автосалон",
    r"не\s+писать\s+с\s+предложени\w*\s+комисси",
    r"не\s+беспокоить\s+с\s+предложени\w*\s+продаж",
    r"комиссионн\w*\s+продаж\w*\s+не\s+интерес",
    r"комисси\w*\s+не\s+интерес",
    r"автосалон\w*\s+не\s+звоните",
)


def find_contact_block(text: str) -> ContactBlock | None:
    normalized = " ".join(text.lower().split())
    if any(re.search(pattern, normalized) for pattern in LEGAL_PATTERNS):
        return ContactBlock("НЕ ПИСАТЬ — обнаружено юридическое обременение.")
    if any(re.search(pattern, normalized) for pattern in DEALER_BAN_PATTERNS):
        return ContactBlock("НЕ ПИСАТЬ — продавец не принимает предложения от автосалонов.")
    return None
