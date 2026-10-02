"""Extra ledenvelden die de beheerder zelf definieert, met validatie per type.

Gevoelige persoonsgegevens (zoals BSN) worden geblokkeerd: zowel als veldnaam als als waarde.
"""

import re
import unicodedata
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledenadmin.domain.errors import ConflictError, NotFoundError
from ledenadmin.domain.models import MemberField, MemberFieldValue


class FieldType(StrEnum):
    TEXT = "tekst"
    NUMBER = "nummer"
    MOBILE = "mobiel"
    IBAN = "iban"
    BOOLEAN = "ja_nee"


FIELD_TYPE_LABELS = {
    FieldType.TEXT: "Tekst",
    FieldType.NUMBER: "Nummer",
    FieldType.MOBILE: "Mobiel nummer",
    FieldType.IBAN: "IBAN",
    FieldType.BOOLEAN: "Ja/nee",
}

LABEL_MAX = 100
VALUE_MAX = 500
BOOLEAN_TRUE = "ja"

# Bijzondere/gevoelige persoonsgegevens (AVG art. 9/10, UAVG art. 46) horen hier niet.
# Hele woorden (kort/dubbelzinnig) en woorddelen; in NL, EN, TR, FR, DE en AR-transliteratie.
_SENSITIVE_WORDS = re.compile(
    r"\b(bsn|sofi|vog|cvv|cvc|pin|ras|race|id|ids|ssn|nin|tckn|tc|nik|din|"
    r"geloof|religion|faith|mezhep|irk|dna|hiv|aids|iris|ziek|sick|"
    r"politics|party|partij|union|parti|kimlik|pasaport|passport|pass|visa|visum|"
    r"nationaliteit|nationality|uyruk|vatandaslik|jinsiya|hawiya)\b"
)
_SENSITIVE_PARTS = (
    # Nationale identificatienummers en ID-bewijzen
    "burgerservice", "sofinummer", "socialsecurity", "nationalid", "nationalnumber",
    "rijksregister", "personalnummer", "personnummer", "steuerid", "tcno", "tckimlik",
    "kimlik", "nufus", "identiteit", "identity", "identite", "ausweis", "idkaart",
    "idcard", "idbewijs", "idnummer", "idnr", "paspoort", "passport", "pasaport",
    "reisepass", "rijbewijs", "driverslicense", "drivinglicense", "ehliyet",
    "documentnummer", "documentnumber", "verblijfsvergunning", "residencepermit",
    "ikamet", "vreemdelingen", "vnummer", "nationaliteit", "nationality",
    # Inlog- en betaalgeheimen
    "wachtwoord", "password", "sifre", "pincode", "creditcard", "kredikarti",
    "cardnumber", "kaartnummer", "cvv", "securitycode",
    # Strafrechtelijk
    "strafblad", "strafrecht", "veroordeling", "criminal", "conviction", "sabika",
    # Gezondheid
    "medisch", "medical", "gezondheid", "health", "saglik", "ziekte", "ziekten",
    "disease", "hastalik", "diagnose", "diagnosis", "handicap", "beperking",
    "disability", "engelli", "allergie", "allergy", "medicijn", "medicatie",
    "medication", "ilac", "zwanger", "pregnan", "bloedgroep", "bloodtype", "kangrubu",
    "psychisch", "mental", "verslaving", "addiction", "zorgverzeker", "insurancenumber",
    # Geloof / levensovertuiging
    "religie", "religion", "religieu", "godsdienst", "geloofs", "levensovertuiging",
    "belief", "inanc", "mezhep", "sekte", "kerkgenootschap", "church",
    # Ras, etniciteit, afkomst
    "etnisch", "etnici", "ethnic", "afkomst", "herkomst", "ethnicorigin",
    "huidskleur", "skincolor",
    # Seksualiteit
    "geaardheid", "orientation", "seksue", "sexual", "cinsel", "yonelim",
    # Politiek en vakbond
    "politiek", "political", "politik", "partijlid", "vakbond", "tradeunion",
    "sendika",
    # Biometrie / genetisch
    "biometri", "vingerafdruk", "fingerprint", "parmakizi", "gezichtsherkenning",
    "faceid", "genetisch", "genetic",
)  # fmt: skip
SENSITIVE_LABEL = (
    "Dit veld lijkt een gevoelig of bijzonder persoonsgegeven (zoals BSN, ID-bewijs, "
    "gezondheid of geloof). Dat mag niet worden vastgelegd (AVG)."
)
SENSITIVE_VALUE = "Dit lijkt een BSN. Een BSN mag niet worden opgeslagen (AVG)."


def _plain(text: str) -> str:
    """Kleine letters zonder accenten (ç→c, ş→s, ı→i, é→e) voor de controle."""
    text = text.lower().replace("ı", "i")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def is_sensitive_label(label: str) -> bool:
    lowered = _plain(label)
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    words = re.sub(r"[^a-z0-9]+", " ", lowered)
    return bool(_SENSITIVE_WORDS.search(words)) or any(p in compact for p in _SENSITIVE_PARTS)


def looks_like_bsn(value: str) -> bool:
    """Negen cijfers die de elfproef voor BSN halen."""
    digits = re.sub(r"[\s.\-]", "", value)
    if not re.fullmatch(r"\d{9}", digits):
        return False
    total = sum(int(d) * w for d, w in zip(digits[:8], range(9, 1, -1))) - int(digits[8])
    return total % 11 == 0 and digits != "000000000"


def _iban(value: str) -> str:
    iban = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        raise ValueError("Vul een geldig IBAN in, bijv. NL91 ABNA 0417 1643 00.")
    number = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    if int(number) % 97 != 1:
        raise ValueError("Dit IBAN klopt niet (controlegetal ongeldig).")
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


def _mobile(value: str) -> str:
    number = re.sub(r"[\s\-().]", "", value)
    if re.fullmatch(r"06\d{8}", number):
        return number
    if re.fullmatch(r"(\+|00)316\d{8}", number):
        return "06" + number[-8:]
    if re.fullmatch(r"\+[1-9]\d{7,14}", number):
        return number
    raise ValueError("Vul een geldig mobiel nummer in, bijv. 06 12345678 of +32 470 123456.")


def _number(value: str) -> str:
    number = value.replace(" ", "")
    if not re.fullmatch(r"-?\d+([.,]\d+)?", number):
        raise ValueError("Vul alleen een getal in.")
    return number


def normalize(field_type: str, value: str) -> str:
    """Controleert en normaliseert een waarde; geeft '' terug voor leeg. ValueError bij fouten."""
    value = value.strip()
    if field_type == FieldType.BOOLEAN:
        return BOOLEAN_TRUE if value else ""
    if not value:
        return ""
    if len(value) > VALUE_MAX:
        raise ValueError(f"Maximaal {VALUE_MAX} tekens.")
    if field_type in (FieldType.TEXT, FieldType.NUMBER) and looks_like_bsn(value):
        raise ValueError(SENSITIVE_VALUE)
    if field_type == FieldType.IBAN:
        return _iban(value)
    if field_type == FieldType.MOBILE:
        return _mobile(value)
    if field_type == FieldType.NUMBER:
        return _number(value)
    return value


def form_name(field: MemberField) -> str:
    return f"veld_{field.id}"


class MemberFieldService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, include_inactive: bool = False) -> list[MemberField]:
        stmt = select(MemberField).order_by(MemberField.id)
        if not include_inactive:
            stmt = stmt.where(MemberField.is_active.is_(True))
        fields = list(self._session.scalars(stmt))
        # Velden van vóór de blokkade die toch gevoelig zijn, worden nooit meer getoond/ingevuld.
        return (
            fields if include_inactive else [f for f in fields if not is_sensitive_label(f.label)]
        )

    def get(self, field_id: int) -> MemberField:
        field = self._session.get(MemberField, field_id)
        if field is None:
            raise NotFoundError(f"Veld {field_id} bestaat niet")
        return field

    def create(self, label: str, field_type: str) -> MemberField:
        label = " ".join(label.split())
        if not label or len(label) > LABEL_MAX:
            raise ConflictError(f"Vul een naam in (maximaal {LABEL_MAX} tekens).", field="label")
        if is_sensitive_label(label):
            raise ConflictError(SENSITIVE_LABEL, field="label")
        if field_type not in set(FieldType):
            raise ConflictError("Kies een geldig type.", field="field_type")
        field = MemberField(label=label, field_type=field_type)
        self._session.add(field)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("Er bestaat al een veld met deze naam.", field="label") from exc
        return field

    def set_active(self, field_id: int, is_active: bool) -> MemberField:
        field = self.get(field_id)
        field.is_active = is_active
        self._session.commit()
        return field

    def delete(self, field_id: int) -> None:
        field = self.get(field_id)
        self._session.execute(delete(MemberFieldValue).where(MemberFieldValue.field_id == field_id))
        self._session.delete(field)
        self._session.commit()

    def values(self, member_id: int) -> dict[int, str]:
        rows = self._session.scalars(
            select(MemberFieldValue).where(MemberFieldValue.member_id == member_id)
        )
        return {row.field_id: row.value for row in rows}

    def validate(self, raw: dict[str, str]) -> tuple[dict[int, str], dict[str, str]]:
        """Controleert formulierwaarden (sleutel `veld_<id>`) voor alle actieve velden."""
        values: dict[int, str] = {}
        errors: dict[str, str] = {}
        for field in self.list():
            name = form_name(field)
            try:
                values[field.id] = normalize(field.field_type, raw.get(name, ""))
            except ValueError as exc:
                errors[name] = str(exc)
        return values, errors

    def save(self, member_id: int, values: dict[int, str]) -> None:
        for field_id, value in values.items():
            existing = self._session.get(MemberFieldValue, (member_id, field_id))
            if value and existing:
                existing.value = value
            elif value:
                self._session.add(
                    MemberFieldValue(member_id=member_id, field_id=field_id, value=value)
                )
            elif existing:
                self._session.delete(existing)
        self._session.commit()
