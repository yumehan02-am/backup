import argparse
import csv
import json
import os
import re
import sys
import tempfile
import urllib.request
import textwrap
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import chardet
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None


APP_TITLE = "メルカリ ヤマトB2出荷リスト作成"
DEFAULT_ITEM_NAME = "衣料品(メルカリS)"
ADDRESS_DETAIL_LIMIT = 16
ADDRESS_OVERFLOW_FIELDS = 3
POSTAL_DATA_DIR = "postal_data"
POSTAL_DATA_FILE = "utf_ken_all.csv"
POSTAL_DATA_URL = "https://www.post.japanpost.jp/service/search/zipcode/download/utf/zip/utf_ken_all.zip"
UPLOAD_MESSAGE_CONFIG = "upload_message_config.json"
SHIPPING_MESSAGE_TEMPLATE_CSV = "shipping_message_templates.csv"
SHIPPING_EVENT_TEMPLATE_CSV = "shipping_event_templates.csv"
INVOICE_TYPE_CONFIG = "invoice_type_config.json"
APP_SETTINGS_CONFIG = "app_settings.json"
SESSION_CONFIG = "current_session.json"

SENDER = {
    "code": "1",
    "name": "夢企覚販売(有)",
    "phone": "0666243791",
    "postal_code": "546-0043",
    "address": "大阪府大阪市東住吉区駒川3-22-17",
    "billing_code": "066629619802",
    "freight_management_number": "01",
    "default_item_name": DEFAULT_ITEM_NAME,
}
SENDER_SETTINGS = dict(SENDER)

DEFAULT_INVOICE_TYPE_SETTINGS = [
    {"code": "A", "name": "ネコポス", "upload_name": "ヤマト運輸 ネコポス", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": True},
    {"code": "0", "name": "発払", "upload_name": "ヤマト運輸 宅急便", "input_keywords": "宅配便", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "2", "name": "コレクト", "upload_name": "ヤマト運輸 宅急便(コレクト)", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "3", "name": "ＤＭ便", "upload_name": "ヤマト運輸 DM便", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "4", "name": "タイム ※B2Ver6、B2Ver7のみ利用可能", "upload_name": "ヤマト運輸 タイム", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "5", "name": "着払 ※B2Ver6、B2Ver7のみ利用可能", "upload_name": "ヤマト運輸 着払", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "8", "name": "宅急便コンパクト", "upload_name": "ヤマト運輸 宅急便コンパクト", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "9", "name": "宅急便コンパクトコレクト", "upload_name": "ヤマト運輸 宅急便コンパクトコレクト", "input_keywords": "", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "default": False},
    {"code": "SG", "name": "佐川急便 宅配便", "upload_name": "佐川急便 飛脚宅配便", "input_keywords": "佐川急便,飛脚宅配便", "item_name": "", "cool_type": "", "handling1": "", "handling2": "", "article": "", "carrier_id": "sagawa", "ehiden_speed_code": "000", "ehiden_cool_code": "001", "ehiden_package_code": "001", "ehiden_mototyaku_type": "", "default": False},
]
INVOICE_TYPE_SETTINGS = json.loads(json.dumps(DEFAULT_INVOICE_TYPE_SETTINGS, ensure_ascii=False))
INVOICE_TYPES = [(item["code"], item["name"]) for item in INVOICE_TYPE_SETTINGS]
INVOICE_TYPE_LABELS = [f"{code} : {name}" for code, name in INVOICE_TYPES]
INVOICE_TYPE_NAMES = dict(INVOICE_TYPES)
SHIPPING_METHOD_NAMES = {item["code"]: item["upload_name"] for item in INVOICE_TYPE_SETTINGS}
INVOICE_INPUT_KEYWORDS = {item["code"]: item.get("input_keywords", "") for item in INVOICE_TYPE_SETTINGS}
DEFAULT_INVOICE_CODE = "A"
DEFAULT_UPLOAD_MESSAGES = {
    "before": "ご注文ありがとうございます。発送の詳細をお知らせいたします。",
    "after": "お荷物の配送状況はヤマト運輸追跡サービスをご利用ください。",
    "combined": "複数のご注文を同梱で発送いたしました。",
    "multiple": "複数のお荷物での発送となります。",
    "method_messages": {
        "A": "ポスト投函でのお届けとなります。",
        "0": "",
        "2": "代金引換でのお届けとなります。",
        "3": "ポスト投函でのお届けとなります。",
        "4": "",
        "5": "着払いでのお届けとなります。",
        "8": "宅急便コンパクトでのお届けとなります。",
        "9": "宅急便コンパクトコレクトでのお届けとなります。",
    },
}
DEFAULT_EVENT_TEMPLATE_ROWS = [
    {"event": "before", "label": "冒頭文", "message": DEFAULT_UPLOAD_MESSAGES["before"], "enabled": "1"},
    {"event": "combined", "label": "同梱発送文", "message": DEFAULT_UPLOAD_MESSAGES["combined"], "enabled": "1"},
    {"event": "multiple", "label": "分割発送文", "message": DEFAULT_UPLOAD_MESSAGES["multiple"], "enabled": "1"},
    {"event": "after", "label": "末尾文", "message": DEFAULT_UPLOAD_MESSAGES["after"], "enabled": "1"},
]

DELIVERY_TIME_TYPES = [
    ("", "指定なし"),
    ("0812", "午前中"),
    ("1416", "14時から16時"),
    ("1618", "16時から18時"),
    ("1820", "18時から20時"),
    ("1921", "19時から21時"),
]
DELIVERY_TIME_LABELS = [f"{code} : {name}" if code else name for code, name in DELIVERY_TIME_TYPES]
DELIVERY_TIME_NAMES = dict(DELIVERY_TIME_TYPES)

PDF_FONT_OPTIONS = {
    "メイリオ": r"C:\Windows\Fonts\meiryo.ttc",
    "游ゴシック": r"C:\Windows\Fonts\YuGothM.ttc",
    "MS ゴシック": r"C:\Windows\Fonts\msgothic.ttc",
    "BIZ UDゴシック": r"C:\Windows\Fonts\BIZ-UDGothicR.ttc",
    "游明朝": r"C:\Windows\Fonts\YuMincho.ttc",
    "MS 明朝": r"C:\Windows\Fonts\msmincho.ttc",
    "BIZ UD明朝": r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc",
}
PDF_FONT_SIZE_OPTIONS = [str(size) for size in range(18, 49)]
DEFAULT_APP_SETTINGS = {
    "pdf_font_size": 32,
    "pdf_font_name": "メイリオ",
    "postal_data_url": POSTAL_DATA_URL,
}

B2_HEADERS = [
    "お客様管理番号", "送り状種類", "クール区分", "伝票番号", "出荷予定日", "お届け予定日", "配達時間帯",
    "お届け先コード", "お届け先電話番号", "お届け先電話番号枝番", "お届け先郵便番号", "お届け先住所",
    "お届け先アパートマンション名", "お届け先会社・部門１", "お届け先会社・部門２", "お届け先名", "お届け先名(ｶﾅ)",
    "敬称", "ご依頼主コード", "ご依頼主電話番号", "ご依頼主電話番号枝番", "ご依頼主郵便番号", "ご依頼主住所",
    "ご依頼主アパートマンション", "ご依頼主名", "ご依頼主名(ｶﾅ)", "品名コード１", "品名１", "品名コード２",
    "品名２", "荷扱い１", "荷扱い２", "記事", "ｺﾚｸﾄ代金引換額（税込)", "内消費税額等", "止置き",
    "営業所コード", "発行枚数", "個数口表示フラグ", "請求先顧客コード", "請求先分類コード", "運賃管理番号",
    "クロネコwebコレクトデータ登録", "クロネコwebコレクト加盟店番号", "クロネコwebコレクト申込受付番号１",
    "クロネコwebコレクト申込受付番号２", "クロネコwebコレクト申込受付番号３", "お届け予定ｅメール利用区分",
    "お届け予定ｅメールe-mailアドレス", "入力機種", "お届け予定ｅメールメッセージ", "お届け完了ｅメール利用区分",
    "お届け完了ｅメールe-mailアドレス", "お届け完了ｅメールメッセージ", "クロネコ収納代行利用区分", "予備",
    "収納代行請求金額(税込)", "収納代行内消費税額等", "収納代行請求先郵便番号", "収納代行請求先住所",
    "収納代行請求先住所（アパートマンション名）", "収納代行請求先会社・部門名１", "収納代行請求先会社・部門名２",
    "収納代行請求先名(漢字)", "収納代行請求先名(カナ)", "収納代行問合せ先名(漢字)", "収納代行問合せ先郵便番号",
    "収納代行問合せ先住所", "収納代行問合せ先住所（アパートマンション名）", "収納代行問合せ先電話番号",
    "収納代行管理番号", "収納代行品名", "収納代行備考", "複数口くくりキー", "検索キータイトル1", "検索キー1",
    "検索キータイトル2", "検索キー2", "検索キータイトル3", "検索キー3", "検索キータイトル4", "検索キー4",
    "検索キータイトル5", "検索キー5", "予備", "予備", "投函予定メール利用区分", "投函予定メールe-mailアドレス",
    "投函予定メール", "投函完了メール", "投函完了メール", "投函完了メール", "投函完了メール", "投函完了メール",
    "投函完了メール",
]

EHIDEN3_HEADERS = [
    "お届け先コード取得区分", "お届け先コード", "お届け先電話番号", "お届け先郵便番号",
    "お届け先住所１", "お届け先住所２", "お届け先住所３", "お届け先名称１", "お届け先名称２",
    "お客様管理番号", "お客様コード", "部署ご担当者コード取得区分", "部署ご担当者コード", "部署ご担当者名称",
    "荷送人電話番号", "ご依頼主コード取得区分", "ご依頼主コード", "ご依頼主電話番号", "ご依頼主郵便番号",
    "ご依頼主住所１", "ご依頼主住所２", "ご依頼主名称１", "ご依頼主名称２", "荷姿",
    "品名１", "品名２", "品名３", "品名４", "品名５", "荷札荷姿",
    "荷札品名１", "荷札品名２", "荷札品名３", "荷札品名４", "荷札品名５", "荷札品名６",
    "荷札品名７", "荷札品名８", "荷札品名９", "荷札品名１０", "荷札品名１１",
    "出荷個数", "スピード指定", "クール便指定", "配達日", "配達指定時間帯", "配達指定時間（時分）",
    "代引金額", "消費税", "決済種別", "保険金額", "指定シール１", "指定シール２", "指定シール３",
    "営業所受取", "SRC区分", "営業所受取営業店コード", "元着区分", "メールアドレス", "ご不在時連絡先",
    "出荷日", "お問い合せ送り状No.", "出荷場印字区分", "集約解除指定",
    "編集０１", "編集０２", "編集０３", "編集０４", "編集０５", "編集０６", "編集０７", "編集０８", "編集０９", "編集１０",
]

EHIDEN_TIME_CODES = {
    "0812": "01",
    "1214": "12",
    "1416": "14",
    "1618": "16",
    "1820": "18",
    "1821": "04",
    "1921": "19",
}

REQUIRED_COLUMNS = [
    "order_id", "purchase_date", "buyer_name", "product_name", "quantity", "product_price",
    "shipping_method", "shipping_postal_code", "shipping_state", "shipping_city",
    "shipping_address_1", "shipping_name", "shipping_phone_number",
]


@dataclass
class OrderRecord:
    source: Dict[str, str]
    invoice_type: str = "A"
    copies: int = 1
    delivery_date: str = ""
    delivery_time: str = ""
    selected: bool = True
    done: bool = False
    bundle_id: str = ""
    note: str = ""
    row_id: str = field(default="")

    def value(self, key: str) -> str:
        return clean(self.source.get(key, ""))


@dataclass
class UploadRecord:
    order: OrderRecord
    process_type: str = "通常"
    group_id: str = ""
    tracking_numbers: List[str] = field(default_factory=list)
    adopted_tracking: str = ""
    upload: bool = True
    done: bool = False

    def order_id(self) -> str:
        return self.order.value("order_id")

    def tracking_text(self) -> str:
        return " / ".join([t for t in self.tracking_numbers if t])


class PostalCodeDatabase:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.by_zip: Dict[str, List[Dict[str, str]]] = {}
        self.loaded = False
        self.error = ""
        self.load()

    def load(self) -> None:
        try:
            with self.csv_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.reader(f):
                    if len(row) < 9:
                        continue
                    zipcode = normalize_postal(row[2])
                    if not zipcode:
                        continue
                    self.by_zip.setdefault(zipcode, []).append({
                        "state": clean(row[6]),
                        "city": clean(row[7]),
                        "town": clean(row[8]),
                    })
            self.loaded = True
        except Exception as e:
            self.error = str(e)

    def lookup(self, postal_code: str) -> List[Dict[str, str]]:
        return self.by_zip.get(normalize_postal(postal_code), [])

    def find_by_address(self, state: str, city: str, rest: str, limit: int = 30) -> List[Dict[str, str]]:
        state = clean(state)
        city = clean(city)
        rest = clean(rest)
        results = []
        for zipcode, rows in self.by_zip.items():
            for row in rows:
                if state and row["state"] != state:
                    continue
                if city and not (row["city"] == city or city.startswith(row["city"]) or row["city"].startswith(city)):
                    continue
                if rest and row["town"] and row["town"] not in rest and rest not in row["town"]:
                    continue
                item = {"zipcode": zipcode, **row}
                results.append(item)
                if len(results) >= limit:
                    return results
        return results

    def summary(self) -> str:
        if self.loaded:
            return f"郵便番号DB: {self.csv_path.name} ({len(self.by_zip):,}件)"
        if self.error:
            return f"郵便番号DB読込エラー: {self.error}"
        return "郵便番号DBなし"


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).replace('"', "").strip()


def gui_preview(value: str, limit: int = 80) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def joined_tracking_numbers(numbers: List[str]) -> str:
    return " / ".join([clean(number) for number in numbers if clean(number)])


def normalize_postal(value: str) -> str:
    digits = re.sub(r"\D", "", clean(value))
    return digits if len(digits) == 7 else ""


def normalize_invoice_settings(settings: List[Dict[str, object]]) -> List[Dict[str, object]]:
    normalized = []
    seen = set()
    default_by_code = {clean(item.get("code", "")): item for item in DEFAULT_INVOICE_TYPE_SETTINGS}
    source_items = list(settings or [])
    for default_item in DEFAULT_INVOICE_TYPE_SETTINGS:
        default_code = clean(default_item.get("code", ""))
        if default_code and not any(clean(item.get("code", "")) == default_code for item in source_items):
            source_items.append(default_item)
    for item in source_items:
        code = clean(item.get("code", ""))
        name = clean(item.get("name", ""))
        if not code or not name or code in seen:
            continue
        seen.add(code)
        default_item = default_by_code.get(code, {})
        upload_name = clean(item.get("upload_name", "")) or clean(default_item.get("upload_name", "")) or f"ヤマト運輸({code})"
        normalized.append({
            "code": code,
            "name": name,
            "upload_name": upload_name,
            "input_keywords": clean(item.get("input_keywords", "")) or clean(default_item.get("input_keywords", "")),
            "item_name": clean(item.get("item_name", "")) or clean(default_item.get("item_name", "")),
            "cool_type": clean(item.get("cool_type", "")) or clean(default_item.get("cool_type", "")),
            "handling1": clean(item.get("handling1", "")) or clean(default_item.get("handling1", "")),
            "handling2": clean(item.get("handling2", "")) or clean(default_item.get("handling2", "")),
            "article": clean(item.get("article", "")) or clean(default_item.get("article", "")),
            "carrier_id": clean(item.get("carrier_id", "")) or clean(default_item.get("carrier_id", "")) or "yamato",
            "ehiden_speed_code": clean(item.get("ehiden_speed_code", "")) or clean(default_item.get("ehiden_speed_code", "")),
            "ehiden_cool_code": clean(item.get("ehiden_cool_code", "")) or clean(default_item.get("ehiden_cool_code", "")),
            "ehiden_package_code": clean(item.get("ehiden_package_code", "")) or clean(default_item.get("ehiden_package_code", "")),
            "ehiden_mototyaku_type": clean(item.get("ehiden_mototyaku_type", "")) or clean(default_item.get("ehiden_mototyaku_type", "")),
            "ehiden_label1": clean(item.get("ehiden_label1", "")) or clean(default_item.get("ehiden_label1", "")),
            "ehiden_label2": clean(item.get("ehiden_label2", "")) or clean(default_item.get("ehiden_label2", "")),
            "ehiden_label3": clean(item.get("ehiden_label3", "")) or clean(default_item.get("ehiden_label3", "")),
            "default": bool(item.get("default", False)),
        })
    if not normalized:
        normalized = json.loads(json.dumps(DEFAULT_INVOICE_TYPE_SETTINGS, ensure_ascii=False))
    if not any(item.get("default") for item in normalized):
        normalized[0]["default"] = True
    return normalized


def normalize_sender_settings(settings: Dict[str, object]) -> Dict[str, str]:
    source = dict(SENDER)
    if isinstance(settings, dict):
        source.update(settings)
    return {
        "code": clean(source.get("code", "")),
        "name": clean(source.get("name", "")),
        "phone": clean(source.get("phone", "")),
        "postal_code": clean(source.get("postal_code", "")),
        "address": clean(source.get("address", "")),
        "billing_code": clean(source.get("billing_code", "")),
        "freight_management_number": clean(source.get("freight_management_number", "")),
        "default_item_name": clean(source.get("default_item_name", "")) or DEFAULT_ITEM_NAME,
    }


def apply_sender_settings(settings: Dict[str, object]) -> None:
    global SENDER_SETTINGS
    SENDER_SETTINGS = normalize_sender_settings(settings)


def apply_invoice_settings(settings: List[Dict[str, object]]) -> None:
    global INVOICE_TYPE_SETTINGS, INVOICE_TYPES, INVOICE_TYPE_LABELS, INVOICE_TYPE_NAMES
    global SHIPPING_METHOD_NAMES, INVOICE_INPUT_KEYWORDS, DEFAULT_INVOICE_CODE
    INVOICE_TYPE_SETTINGS = normalize_invoice_settings(settings)
    INVOICE_TYPES = [(item["code"], item["name"]) for item in INVOICE_TYPE_SETTINGS]
    INVOICE_TYPE_LABELS = [f"{code} : {name}" for code, name in INVOICE_TYPES]
    INVOICE_TYPE_NAMES = dict(INVOICE_TYPES)
    SHIPPING_METHOD_NAMES = {item["code"]: item["upload_name"] for item in INVOICE_TYPE_SETTINGS}
    INVOICE_INPUT_KEYWORDS = {item["code"]: item.get("input_keywords", "") for item in INVOICE_TYPE_SETTINGS}
    DEFAULT_INVOICE_CODE = next((item["code"] for item in INVOICE_TYPE_SETTINGS if item.get("default")), INVOICE_TYPE_SETTINGS[0]["code"])


def load_invoice_settings(base_dir: Path) -> List[Dict[str, object]]:
    path = base_dir / INVOICE_TYPE_CONFIG
    if not path.exists():
        apply_sender_settings(SENDER)
        return normalize_invoice_settings(DEFAULT_INVOICE_TYPE_SETTINGS)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            apply_sender_settings(data.get("sender", SENDER))
            data = data.get("invoice_types", [])
        else:
            apply_sender_settings(SENDER)
        if isinstance(data, list):
            return normalize_invoice_settings(data)
    except Exception:
        pass
    apply_sender_settings(SENDER)
    return normalize_invoice_settings(DEFAULT_INVOICE_TYPE_SETTINGS)


def save_invoice_settings(base_dir: Path, settings: List[Dict[str, object]], sender_settings: Optional[Dict[str, object]] = None) -> None:
    path = base_dir / INVOICE_TYPE_CONFIG
    sender = normalize_sender_settings(sender_settings if sender_settings is not None else SENDER_SETTINGS)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"sender": sender, "invoice_types": normalize_invoice_settings(settings)}, f, ensure_ascii=False, indent=2)


def invoice_setting(code: str) -> Dict[str, object]:
    code = invoice_code(code)
    return next((item for item in INVOICE_TYPE_SETTINGS if item.get("code") == code), {})


def ensure_upload_message_methods(config: Dict[str, object]) -> None:
    messages = config.setdefault("method_messages", {})
    if not isinstance(messages, dict):
        messages = {}
        config["method_messages"] = messages
    defaults = DEFAULT_UPLOAD_MESSAGES.get("method_messages", {})
    for code, _name in INVOICE_TYPES:
        messages.setdefault(code, defaults.get(code, ""))


def infer_invoice_type_from_shipping_method(method: str) -> str:
    value = clean(method)
    for code, keywords in INVOICE_INPUT_KEYWORDS.items():
        for keyword in re.split(r"[,，、/／\s]+", clean(keywords)):
            if keyword and keyword == value:
                return code
    return DEFAULT_INVOICE_CODE


def invoice_label(code: str) -> str:
    code = clean(code)
    return f"{code} : {INVOICE_TYPE_NAMES.get(code, code)}" if code else ""


def invoice_code(label_or_code: str) -> str:
    value = clean(label_or_code)
    if " : " in value:
        return value.split(" : ", 1)[0].strip()
    return value


def delivery_time_label(code: str) -> str:
    code = clean(code)
    if not code:
        return "指定なし"
    return f"{code} : {DELIVERY_TIME_NAMES.get(code, code)}"


def delivery_time_code(label_or_code: str) -> str:
    value = clean(label_or_code)
    if value == "指定なし":
        return ""
    if " : " in value:
        return value.split(" : ", 1)[0].strip()
    return value


def detect_encoding(path: Path) -> str:
    data = path.read_bytes()[:65536]
    guess = chardet.detect(data)
    enc = guess.get("encoding") or "utf-8-sig"
    return "utf-8-sig" if enc.lower().replace("-", "") in {"utf8", "utf8sig"} else enc


def read_orders(path: Path) -> List[OrderRecord]:
    encoding = detect_encoding(path)
    with path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("CSVに必要な列がありません: " + ", ".join(missing))
        orders = []
        for idx, row in enumerate(reader, start=1):
            if not clean(row.get("order_id")):
                continue
            method = clean(row.get("shipping_method"))
            invoice_type = infer_invoice_type_from_shipping_method(method)
            selected = bool(clean(row.get("shipping_name")))
            orders.append(OrderRecord(row, invoice_type=invoice_type, copies=1, selected=selected, row_id=str(idx)))
        return orders


def load_upload_messages(base_dir: Path) -> Dict[str, object]:
    path = base_dir / UPLOAD_MESSAGE_CONFIG
    config = json.loads(json.dumps(DEFAULT_UPLOAD_MESSAGES, ensure_ascii=False))
    if not path.exists():
        ensure_upload_message_methods(config)
        return config
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        for key in ["before", "after", "combined", "multiple"]:
            if key in loaded:
                config[key] = loaded[key]
        config["method_messages"].update(loaded.get("method_messages", {}))
    except Exception:
        pass
    ensure_upload_message_methods(config)
    return config


def save_upload_messages(base_dir: Path, config: Dict[str, object]) -> None:
    path = base_dir / UPLOAD_MESSAGE_CONFIG
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def template_to_gui(value: str) -> str:
    return str(value or "").replace("\\n", "\n")


def template_to_csv(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def template_enabled(value) -> bool:
    return clean(value).lower() not in {"", "0", "false", "off", "no", "無効"}


def default_method_template_rows(upload_messages: Optional[Dict[str, object]] = None) -> List[Dict[str, str]]:
    upload_messages = upload_messages or DEFAULT_UPLOAD_MESSAGES
    method_messages = upload_messages.get("method_messages", {}) if isinstance(upload_messages, dict) else {}
    rows = []
    for code, name in INVOICE_TYPES:
        upload_name = SHIPPING_METHOD_NAMES.get(code, f"ヤマト運輸({code})")
        parts = upload_name.split(maxsplit=1)
        carrier = parts[0] if parts else "ヤマト運輸"
        method = parts[1] if len(parts) > 1 else INVOICE_TYPE_NAMES.get(code, name)
        rows.append({
            "invoice_code": code,
            "carrier": carrier,
            "method": method,
            "message1": "",
            "tracking_label": "{carrier} {method}：{tracking}",
            "message2": str(method_messages.get(code, "")),
            "no_tracking_message": "未登録",
            "enabled": "1",
        })
    return rows


def default_event_template_rows(upload_messages: Optional[Dict[str, object]] = None) -> List[Dict[str, str]]:
    upload_messages = upload_messages or DEFAULT_UPLOAD_MESSAGES
    rows = []
    for row in DEFAULT_EVENT_TEMPLATE_ROWS:
        item = dict(row)
        key = item["event"]
        if isinstance(upload_messages, dict) and key in upload_messages:
            item["message"] = str(upload_messages.get(key, ""))
        rows.append(item)
    return rows


def read_template_csv(path: Path, fieldnames: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({key: template_to_gui(row.get(key, "")) for key in fieldnames})
    return rows


def write_template_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: template_to_csv(row.get(key, "")) for key in fieldnames})


def load_message_templates(base_dir: Path, upload_messages: Optional[Dict[str, object]] = None) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    method_fields = ["invoice_code", "carrier", "method", "message1", "tracking_label", "message2", "no_tracking_message", "enabled"]
    event_fields = ["event", "label", "message", "enabled"]
    method_path = base_dir / SHIPPING_MESSAGE_TEMPLATE_CSV
    event_path = base_dir / SHIPPING_EVENT_TEMPLATE_CSV
    method_rows = read_template_csv(method_path, method_fields)
    event_rows = read_template_csv(event_path, event_fields)
    if not method_rows:
        method_rows = default_method_template_rows(upload_messages)
        write_template_csv(method_path, method_fields, method_rows)
    if not event_rows:
        event_rows = default_event_template_rows(upload_messages)
        write_template_csv(event_path, event_fields, event_rows)
    existing_codes = {clean(row.get("invoice_code", "")) for row in method_rows}
    for row in default_method_template_rows(upload_messages):
        if row["invoice_code"] not in existing_codes:
            method_rows.append(row)
    existing_events = {clean(row.get("event", "")) for row in event_rows}
    for row in default_event_template_rows(upload_messages):
        if row["event"] not in existing_events:
            event_rows.append(row)
    return method_rows, event_rows


def save_message_templates(base_dir: Path, method_rows: List[Dict[str, str]], event_rows: List[Dict[str, str]]) -> None:
    write_template_csv(
        base_dir / SHIPPING_MESSAGE_TEMPLATE_CSV,
        ["invoice_code", "carrier", "method", "message1", "tracking_label", "message2", "no_tracking_message", "enabled"],
        method_rows,
    )
    write_template_csv(
        base_dir / SHIPPING_EVENT_TEMPLATE_CSV,
        ["event", "label", "message", "enabled"],
        event_rows,
    )


def load_app_settings(base_dir: Path) -> Dict[str, object]:
    settings = dict(DEFAULT_APP_SETTINGS)
    path = base_dir / APP_SETTINGS_CONFIG
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                settings.update(loaded)
        except Exception:
            pass
    try:
        settings["pdf_font_size"] = max(18, min(48, int(settings.get("pdf_font_size", 32))))
    except Exception:
        settings["pdf_font_size"] = 32
    if settings.get("pdf_font_name") not in PDF_FONT_OPTIONS:
        settings["pdf_font_name"] = "メイリオ"
    if not clean(settings.get("postal_data_url", "")):
        settings["postal_data_url"] = POSTAL_DATA_URL
    return settings


def save_app_settings(base_dir: Path, settings: Dict[str, object]) -> None:
    path = base_dir / APP_SETTINGS_CONFIG
    with path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def session_path(base_dir: Path) -> Path:
    return base_dir / SESSION_CONFIG


def read_b2_result_rows(path: Path) -> List[List[str]]:
    encoding = detect_encoding(path)
    try_encodings = [encoding, "cp932", "utf-8-sig"]
    last_error = None
    for enc in try_encodings:
        try:
            with path.open("r", encoding=enc, errors="ignore", newline="") as f:
                rows = list(csv.reader(f))
            if rows and rows[0] and rows[0][0] == "お客様管理番号":
                rows = rows[1:]
            return [row for row in rows if len(row) >= 16 and clean(row[0]).startswith("order_")]
        except Exception as e:
            last_error = e
    raise ValueError(f"B2出荷データを読み込めませんでした: {last_error}")


def split_address(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> tuple[str, str, str, str]:
    state, city, address1, address2 = normalized_address_fields(record, postal_db)
    main_rest = address1[:ADDRESS_DETAIL_LIMIT]
    overflow = address1[ADDRESS_DETAIL_LIMIT:] + address2
    apartment = overflow[:ADDRESS_DETAIL_LIMIT]
    department1 = overflow[ADDRESS_DETAIL_LIMIT:ADDRESS_DETAIL_LIMIT * 2]
    department2 = overflow[ADDRESS_DETAIL_LIMIT * 2:ADDRESS_DETAIL_LIMIT * 3]
    return state + city + main_rest, apartment, department1, department2


def address_overflow(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> str:
    _, _, address1, address2 = normalized_address_fields(record, postal_db)
    overflow = address1[ADDRESS_DETAIL_LIMIT:] + address2
    return overflow[ADDRESS_DETAIL_LIMIT * ADDRESS_OVERFLOW_FIELDS:]


def normalized_address_fields(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> tuple[str, str, str, str]:
    state = record.value("shipping_state")
    city = record.value("shipping_city")
    address1 = record.value("shipping_address_1")
    address2 = record.value("shipping_address_2")
    candidates = postal_db.lookup(record.value("shipping_postal_code")) if postal_db and postal_db.loaded else []
    for candidate in candidates:
        db_state = candidate["state"]
        db_city = candidate["city"]
        if state != db_state:
            continue
        if city == db_city:
            return state, city, address1, address2
        if city.startswith(db_city):
            extra_town = city[len(db_city):]
            return state, db_city, extra_town + address1, address2
        if db_city.startswith(city):
            missing_city_part = db_city[len(city):]
            if missing_city_part and address1.startswith(missing_city_part):
                return state, db_city, address1[len(missing_city_part):], address2
    return state, city, address1, address2


def normalized_address_parts(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> tuple[str, str, str]:
    state, city, address1, address2 = normalized_address_fields(record, postal_db)
    return state, city, address1 + address2


def format_delivery_address(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> str:
    parts = [record.value("shipping_postal_code")]
    parts.extend([part for part in split_address(record, postal_db) if part])
    return "\n".join(parts).strip()


def recipient_group_key(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> tuple:
    state, city, rest = normalized_address_parts(record, postal_db)
    return (
        record.value("shipping_name"),
        normalize_postal(record.value("shipping_postal_code")),
        state,
        city,
        rest,
        record.value("shipping_phone_number"),
    )


def validate_record(record: OrderRecord, postal_db: Optional[PostalCodeDatabase] = None) -> List[str]:
    warnings = []
    postal = record.value("shipping_postal_code")
    state = record.value("shipping_state")
    city = record.value("shipping_city")
    address1 = record.value("shipping_address_1")
    if not normalize_postal(postal):
        warnings.append("郵便番号の形式が不正")
    if not state:
        warnings.append("都道府県が空欄")
    if not city:
        warnings.append("市区町村が空欄")
    if not record.value("shipping_name"):
        warnings.append("未入金のため出荷不可")
    if postal_db and postal_db.loaded and normalize_postal(postal):
        candidates = postal_db.lookup(postal)
        if not candidates:
            warnings.append("郵便番号がDBに存在しません")
        else:
            state_matches = [c for c in candidates if c["state"] == state]
            city_matches = [c for c in state_matches if c["city"] == city]
            if not state_matches:
                expected = " / ".join(sorted({c["state"] for c in candidates})[:3])
                warnings.append(f"郵便番号と都道府県が不一致(DB: {expected})")
            elif not city_matches:
                auto_fixable = any(
                    city.startswith(c["city"]) or
                    (c["city"].startswith(city) and address1.startswith(c["city"][len(city):]))
                    for c in state_matches
                )
                if not auto_fixable:
                    expected = " / ".join(sorted({c["city"] for c in state_matches})[:3])
                    warnings.append(f"郵便番号と市区町村が不一致(DB: {expected})")
    if address_overflow(record, postal_db):
        warnings.append("住所が長すぎます。会社・部門2までに収まりません")
    if len(recipient_name(record)) > 32:
        warnings.append("お届け先名が32文字を超えています")
    return warnings


def recipient_name(record: OrderRecord) -> str:
    shipping_name = record.value("shipping_name")
    buyer_name = record.value("buyer_name")
    return shipping_name or buyer_name


def shipping_list_recipient_name(record: OrderRecord) -> str:
    name = recipient_name(record)
    labels = []
    if record.bundle_id:
        labels.append(f"【同梱{record.bundle_id}】")
    if record.copies > 1:
        labels.append("【分割】")
    if labels:
        return "".join(labels) + "\n" + name
    return name


def shipping_check_marker(record: OrderRecord) -> str:
    marker = ""
    if record.bundle_id:
        marker = "同"
    elif record.copies > 1:
        marker = "分"
    return marker


def buyer_order_note(record: OrderRecord, department2: str) -> str:
    shipping_name = record.value("shipping_name")
    buyer_name = record.value("buyer_name")
    if not shipping_name or not buyer_name or shipping_name == buyer_name:
        return department2
    if department2:
        return department2
    return f"[{buyer_name}様注文品]"


def carrier_id_for_record(record: OrderRecord) -> str:
    return clean(invoice_setting(record.invoice_type).get("carrier_id", "")) or "yamato"


def ehiden_manage_no(record: OrderRecord) -> str:
    row_id = clean(record.row_id)
    if row_id.isdigit():
        return f"M{int(row_id):08d}"
    seed = re.sub(r"[^0-9A-Za-z]", "", record.value("order_id"))[-12:] or "0"
    return ("M" + seed)[-16:]


def format_yyyymmdd(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y%m%d")
        except Exception:
            pass
    digits = re.sub(r"\D", "", value)
    return digits[:8] if len(digits) >= 8 else ""


def split_fixed_width(text: str, width: int, count: int) -> List[str]:
    text = clean(text)
    return [text[i * width:(i + 1) * width] for i in range(count)]


def b2_row(record: OrderRecord, ship_date: str, postal_db: Optional[PostalCodeDatabase] = None) -> List[str]:
    address, apartment, department1, department2 = split_address(record, postal_db)
    invoice_conf = invoice_setting(record.invoice_type)
    row = [""] * len(B2_HEADERS)
    row[0] = record.value("order_id")
    row[1] = invoice_code(record.invoice_type)
    row[2] = clean(invoice_conf.get("cool_type", ""))
    row[4] = ship_date
    row[5] = record.delivery_date
    row[6] = delivery_time_code(record.delivery_time)
    row[8] = record.value("shipping_phone_number")
    row[10] = record.value("shipping_postal_code")
    row[11] = address
    row[12] = apartment
    row[13] = department1
    row[14] = buyer_order_note(record, department2)
    row[15] = recipient_name(record)
    row[17] = "様"
    row[18] = SENDER_SETTINGS["code"]
    row[19] = SENDER_SETTINGS["phone"]
    row[21] = SENDER_SETTINGS["postal_code"]
    row[22] = SENDER_SETTINGS["address"]
    row[24] = SENDER_SETTINGS["name"]
    row[27] = clean(invoice_conf.get("item_name", "")) or SENDER_SETTINGS["default_item_name"]
    row[30] = clean(invoice_conf.get("handling1", ""))
    row[31] = clean(invoice_conf.get("handling2", ""))
    row[32] = clean(invoice_conf.get("article", ""))
    row[37] = str(record.copies)
    row[39] = SENDER_SETTINGS["billing_code"]
    row[41] = SENDER_SETTINGS["freight_management_number"]
    return row


def ehiden3_row(record: OrderRecord, ship_date: str, postal_db: Optional[PostalCodeDatabase] = None) -> List[str]:
    invoice_conf = invoice_setting(record.invoice_type)
    state, city, address1, address2 = normalized_address_fields(record, postal_db)
    dest_address_parts = split_fixed_width(state + city + address1 + address2, 16, 3)
    dest_name_parts = split_fixed_width(recipient_name(record), 16, 2)
    sender_address_parts = split_fixed_width(SENDER_SETTINGS["address"], 16, 2)
    sender_name_parts = split_fixed_width(SENDER_SETTINGS["name"], 16, 2)
    row = [""] * len(EHIDEN3_HEADERS)
    row[2] = record.value("shipping_phone_number")
    row[3] = record.value("shipping_postal_code")
    row[4] = dest_address_parts[0]
    row[5] = dest_address_parts[1]
    row[6] = dest_address_parts[2]
    row[7] = dest_name_parts[0]
    row[8] = dest_name_parts[1]
    row[9] = ehiden_manage_no(record)
    row[16] = SENDER_SETTINGS["code"]
    row[17] = SENDER_SETTINGS["phone"]
    row[18] = SENDER_SETTINGS["postal_code"]
    row[19] = sender_address_parts[0]
    row[20] = sender_address_parts[1]
    row[21] = sender_name_parts[0]
    row[22] = sender_name_parts[1]
    row[23] = clean(invoice_conf.get("ehiden_package_code", "")) or "001"
    row[24] = clean(invoice_conf.get("item_name", "")) or SENDER_SETTINGS["default_item_name"]
    row[41] = str(record.copies)
    row[42] = clean(invoice_conf.get("ehiden_speed_code", "")) or "000"
    row[43] = clean(invoice_conf.get("ehiden_cool_code", "")) or "001"
    row[44] = format_yyyymmdd(record.delivery_date)
    row[45] = EHIDEN_TIME_CODES.get(delivery_time_code(record.delivery_time), "")
    row[50] = clean(invoice_conf.get("ehiden_label1", ""))
    row[51] = clean(invoice_conf.get("ehiden_label2", ""))
    row[52] = clean(invoice_conf.get("ehiden_label3", ""))
    row[57] = clean(invoice_conf.get("ehiden_mototyaku_type", ""))
    row[60] = format_yyyymmdd(ship_date)
    return row


def b2_output_records(records: List[OrderRecord]) -> List[OrderRecord]:
    return carrier_output_records(records, "yamato")


def carrier_output_records(records: List[OrderRecord], carrier_id: str) -> List[OrderRecord]:
    output = []
    used_bundle_ids = set()
    for record in records:
        if not record.selected or record.done:
            continue
        if carrier_id_for_record(record) != carrier_id:
            continue
        if record.bundle_id:
            if record.bundle_id in used_bundle_ids:
                continue
            used_bundle_ids.add(record.bundle_id)
        output.append(record)
    return output


def write_b2_csv(path: Path, records: List[OrderRecord], ship_date: str, encoding: str, postal_db: Optional[PostalCodeDatabase] = None) -> None:
    csv_encoding = "utf-8-sig" if encoding == "UTF-8 BOM" else "cp932"
    with path.open("w", encoding=csv_encoding, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(B2_HEADERS)
        for record in b2_output_records(records):
            writer.writerow(b2_row(record, ship_date, postal_db))


def write_b2_csv_for_records(path: Path, records: List[OrderRecord], ship_date: str, encoding: str, postal_db: Optional[PostalCodeDatabase] = None) -> None:
    csv_encoding = "utf-8-sig" if encoding == "UTF-8 BOM" else "cp932"
    with path.open("w", encoding=csv_encoding, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(B2_HEADERS)
        for record in b2_output_records(records):
            writer.writerow(b2_row(record, ship_date, postal_db))


def write_sagawa_ehiden3_csv(path: Path, records: List[OrderRecord], ship_date: str, encoding: str, postal_db: Optional[PostalCodeDatabase] = None) -> None:
    csv_encoding = "utf-8-sig" if encoding == "UTF-8 BOM" else "cp932"
    with path.open("w", encoding=csv_encoding, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(EHIDEN3_HEADERS)
        for record in carrier_output_records(records, "sagawa"):
            writer.writerow(ehiden3_row(record, ship_date, postal_db))


def write_sagawa_manage_map(path: Path, records: List[OrderRecord], encoding: str) -> None:
    csv_encoding = "utf-8-sig" if encoding == "UTF-8 BOM" else "cp932"
    with path.open("w", encoding=csv_encoding, newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["manage_no", "order_id", "row_id"])
        for record in carrier_output_records(records, "sagawa"):
            writer.writerow([ehiden_manage_no(record), record.value("order_id"), record.row_id])


def open_file(path: Path) -> None:
    try:
        os.startfile(str(path))
    except Exception:
        pass


def find_font(size: int, font_name: str = "メイリオ"):
    if ImageFont is None:
        raise RuntimeError("Pillowが利用できないためPDFを作成できません。requirements.txtのPillowをインストールしてください。")
    selected = PDF_FONT_OPTIONS.get(font_name)
    if selected and os.path.exists(selected):
        return ImageFont.truetype(selected, size)
    candidates = [
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\NotoSansCJKjp-Regular.otf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wrap_by_width(text: str, font, width: int, draw, prefer_space_break: bool = False) -> List[str]:
    if not text:
        return [""]
    lines: List[str] = []
    for paragraph in str(text).splitlines() or [""]:
        current = ""
        for ch in paragraph:
            candidate = current + ch
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= width or not current:
                current = candidate
            else:
                if prefer_space_break:
                    space_pos = current.rfind(" ")
                    if space_pos >= 0 and space_pos < len(current) - 1:
                        lines.append(current[:space_pos + 1])
                        current = current[space_pos + 1:] + ch
                    else:
                        lines.append(current)
                        current = ch
                else:
                    lines.append(current)
                    current = ch
        lines.append(current)
    return lines


def fit_text_by_width(text: str, font, width: int, draw) -> str:
    text = clean(text)
    if not text:
        return ""
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= width:
        return text
    suffix = "..."
    current = ""
    for ch in text:
        candidate = current + ch + suffix
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > width:
            break
        current += ch
    return current + suffix if current else suffix


def wrap_by_width_limited(text: str, font, width: int, draw, max_lines: int) -> List[str]:
    original_width_lines = wrap_by_width(text, font, width, draw)
    wrapped: List[str] = []
    for line in original_width_lines:
        wrapped.append(line)
        if len(wrapped) >= max_lines:
            break
    if not wrapped:
        return [""]
    if len(original_width_lines) > max_lines:
        suffix = "..."
        while wrapped[-1] and draw.textbbox((0, 0), wrapped[-1] + suffix, font=font)[2] - draw.textbbox((0, 0), wrapped[-1] + suffix, font=font)[0] > width:
            wrapped[-1] = wrapped[-1][:-1]
        wrapped[-1] = wrapped[-1] + suffix if wrapped[-1] else suffix
    return wrapped


def shipping_pdf_layout(font_size: int = 32) -> Dict[str, object]:
    page_w, page_h = 3508, 2480  # A4 landscape at 300dpi
    margin = 90
    title_h = 90
    base_row_h = 220
    header_h = 64
    font_size = max(18, min(48, int(font_size)))
    line_h = max(24, font_size + 4)
    cell_pad_x = 14
    cell_pad_y = 12
    bottom_limit = page_h - margin
    columns = [
        ("確認", 100), ("No", 110), ("オーダー", 460), ("送付先氏名", 270),
        ("送付先住所", 570), ("商品名", 876), ("価格", 195),
        ("数", 90), ("お届け日時", 289), ("配送", 200), ("枚数", 110),
    ]
    return {
        "page_w": page_w,
        "page_h": page_h,
        "margin": margin,
        "title_h": title_h,
        "base_row_h": base_row_h,
        "header_h": header_h,
        "font_size": font_size,
        "line_h": line_h,
        "cell_pad_x": cell_pad_x,
        "cell_pad_y": cell_pad_y,
        "bottom_limit": bottom_limit,
        "columns": columns,
        "x0": margin,
        "y0": margin + title_h,
    }


def shipping_row_values(record: OrderRecord, idx: int, postal_db: Optional[PostalCodeDatabase]) -> List[str]:
    order_lines = [record.value("order_id"), record.value("purchase_date")]
    shipping_method = record.value("shipping_method")
    if shipping_method == "未定(出品者が手配)":
        order_lines.append("")
    elif shipping_method:
        order_lines.append(shipping_method)
    order_lines.append("注文者：" + record.value("buyer_name"))
    delivery_lines = [record.delivery_date, delivery_time_label(record.delivery_time)]
    if record.note.strip():
        delivery_lines.append("メモ:" + record.note.strip())
    return [
        "　",
        str(idx),
        "\n".join(order_lines),
        shipping_list_recipient_name(record),
        format_delivery_address(record, postal_db),
        record.value("product_name"),
        record.value("product_price") + "\n-" + record.value("coupon_discount_amount"),
        record.value("quantity"),
        "\n".join(delivery_lines).strip(),
        invoice_label(record.invoice_type),
        str(record.copies),
    ]


def shipping_wrapped_lines(draw, values: List[str], columns, font, cell_pad_x: int) -> List[List[str]]:
    result = []
    for value, (label, width) in zip(values, columns):
        lines = []
        usable_width = width - cell_pad_x * 2
        raw_lines = str(value).splitlines() or [""]
        delivery_note_start = None
        if label == "お届け日時" and len(raw_lines) >= 2:
            first_line_is_date = bool(re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", clean(raw_lines[0])))
            if len(raw_lines) >= 3 and first_line_is_date:
                delivery_note_start = 2
            elif not first_line_is_date:
                delivery_note_start = 1
        note_lines_used = 0
        for line_no, line in enumerate(raw_lines):
            if delivery_note_start is not None and line_no >= delivery_note_start:
                remaining_note_lines = max(0, 4 - note_lines_used)
                if remaining_note_lines:
                    note_lines = wrap_by_width_limited(line, font, usable_width, draw, remaining_note_lines)
                    lines.extend(note_lines)
                    note_lines_used += len(note_lines)
            else:
                lines.extend(wrap_by_width(line, font, usable_width, draw, prefer_space_break=(label == "商品名")))
        result.append(lines)
    return result


def shipping_required_row_height(lines_by_col: List[List[str]], base_row_h: int, cell_pad_y: int, line_h: int) -> int:
    max_lines = max((len(lines) for lines in lines_by_col), default=1)
    return max(base_row_h, cell_pad_y * 2 + max_lines * line_h)


def bundled_record_units(records: List[OrderRecord]) -> List[List[OrderRecord]]:
    units: List[List[OrderRecord]] = []
    used_bundle_ids = set()
    for record in records:
        if record.bundle_id:
            if record.bundle_id in used_bundle_ids:
                continue
            used_bundle_ids.add(record.bundle_id)
            units.append([item for item in records if item.bundle_id == record.bundle_id])
        else:
            units.append([record])
    return units


def flatten_record_units(units: List[List[OrderRecord]]) -> List[OrderRecord]:
    return [record for unit in units for record in unit]


def shipping_record_row_height(record: OrderRecord, idx: int, postal_db: Optional[PostalCodeDatabase], draw, layout, font) -> int:
    values = shipping_row_values(record, idx, postal_db)
    lines = shipping_wrapped_lines(draw, values, layout["columns"], font, layout["cell_pad_x"])
    return shipping_required_row_height(lines, layout["base_row_h"], layout["cell_pad_y"], layout["line_h"])


def split_records_by_pdf_pages(records: List[OrderRecord], postal_db: Optional[PostalCodeDatabase] = None, font_size: int = 32, font_name: str = "メイリオ") -> List[List[OrderRecord]]:
    selected = [r for r in records if r.selected and not r.done]
    layout = shipping_pdf_layout(font_size)
    font = find_font(layout["font_size"], font_name)
    dummy = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(dummy)
    y = layout["y0"] + layout["header_h"]
    pages: List[List[OrderRecord]] = [[]]
    row_idx = 1
    for unit in bundled_record_units(selected):
        unit_h = 0
        for offset, record in enumerate(unit):
            unit_h += shipping_record_row_height(record, row_idx + offset, postal_db, draw, layout, font)
        if y + unit_h > layout["bottom_limit"] and pages[-1]:
            pages.append([])
            y = layout["y0"] + layout["header_h"]
        for offset, record in enumerate(unit):
            row_h = shipping_record_row_height(record, row_idx + offset, postal_db, draw, layout, font)
            pages[-1].append(record)
            y += row_h
        row_idx += len(unit)
    return pages if selected else []


def write_shipping_pdf(path: Path, records: List[OrderRecord], ship_date: str, postal_db: Optional[PostalCodeDatabase] = None, font_size: int = 32, font_name: str = "メイリオ") -> None:
    if Image is None:
        raise RuntimeError("Pillowが利用できないためPDFを作成できません。")

    selected = [r for r in records if r.selected and not r.done]
    layout = shipping_pdf_layout(font_size)
    page_w = layout["page_w"]
    page_h = layout["page_h"]
    margin = layout["margin"]
    header_h = layout["header_h"]
    line_h = layout["line_h"]
    cell_pad_x = layout["cell_pad_x"]
    cell_pad_y = layout["cell_pad_y"]
    bottom_limit = layout["bottom_limit"]
    columns = layout["columns"]
    x0 = layout["x0"]
    y0 = layout["y0"]
    font = find_font(layout["font_size"], font_name)
    small = find_font(max(20, layout["font_size"] - 4), font_name)
    title_font = find_font(44, font_name)
    pages = []

    def new_page(page_idx: int):
        img = Image.new("RGB", (page_w, page_h), "white")
        draw = ImageDraw.Draw(img)
        title = f"メルカリショップス 出荷リスト  出荷予定日: {ship_date}  件数: {len(selected)}"
        draw.text((margin, margin), title, fill="black", font=title_font)
        draw.text((page_w - margin - 180, margin + 8), f"{page_idx}", fill="black", font=small)

        x = x0
        for label, width in columns:
            draw.rectangle((x, y0, x + width, y0 + header_h), outline="black", fill=(235, 240, 245))
            draw.text((x + cell_pad_x, y0 + 10), label, fill="black", font=small)
            x += width
        return img, draw, y0 + header_h

    page_idx = 1
    img, draw, y = new_page(page_idx)
    row_idx = 1
    for unit in bundled_record_units(selected):
        unit_h = 0
        for offset, record in enumerate(unit):
            unit_h += shipping_record_row_height(record, row_idx + offset, postal_db, draw, layout, font)
        if y + unit_h > bottom_limit and y > y0 + header_h:
            pages.append(img)
            page_idx += 1
            img, draw, y = new_page(page_idx)

        for offset, record in enumerate(unit):
            values = shipping_row_values(record, row_idx + offset, postal_db)
            lines_by_col = shipping_wrapped_lines(draw, values, columns, font, cell_pad_x)
            row_h = shipping_required_row_height(lines_by_col, layout["base_row_h"], cell_pad_y, line_h)
            x = x0
            for value, lines, (label, width) in zip(values, lines_by_col, columns):
                draw.rectangle((x, y, x + width, y + row_h), outline="black", fill="white")
                if label == "確認":
                    box = 54
                    marker = shipping_check_marker(record)
                    bx = x + (width - box) // 2
                    if marker:
                        marker_bbox = draw.textbbox((0, 0), marker, font=font)
                        marker_w = marker_bbox[2] - marker_bbox[0]
                        marker_h = marker_bbox[3] - marker_bbox[1]
                        marker_x = x + (width - marker_w) // 2
                        marker_y = y + cell_pad_y
                        draw.text((marker_x, marker_y), marker, fill="black", font=font)
                        by = min(y + row_h - box - cell_pad_y, marker_y + marker_h + 58)
                    else:
                        by = y + (row_h - box) // 2
                    draw.rectangle((bx, by, bx + box, by + box), outline="black", width=3)
                else:
                    for line_no, line in enumerate(lines):
                        draw.text((x + cell_pad_x, y + cell_pad_y + line_no * line_h), line, fill="black", font=font)
                x += width
            y += row_h
        row_idx += len(unit)
    pages.append(img)

    pages[0].save(path, "PDF", resolution=300.0, save_all=True, append_images=pages[1:])


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x760")
        self.records: List[OrderRecord] = []
        self.upload_records: List[UploadRecord] = []
        self.upload_group_counter = 1
        self.bundle_counter = 1
        self.last_warning_count = 0
        self.postal_db = self.load_postal_db()
        self.edit_widget = None
        self.edit_context = None
        self.last_edit_context = None
        self.csv_path = tk.StringVar()
        self.ship_date = tk.StringVar(value=datetime.now().strftime("%Y/%m/%d"))
        self.encoding = tk.StringVar(value="Shift_JIS(cp932)")
        self.group_candidates = tk.BooleanVar(value=False)
        self.app_settings = load_app_settings(Path(__file__).resolve().parent)
        self.pdf_font_size = tk.StringVar(value=str(self.app_settings["pdf_font_size"]))
        self.pdf_font_name = tk.StringVar(value=str(self.app_settings["pdf_font_name"]))
        self.split_b2_by_pdf = tk.BooleanVar(value=False)
        self.split_pdf_pages = tk.IntVar(value=1)
        apply_invoice_settings(load_invoice_settings(Path(__file__).resolve().parent))
        self.upload_messages = load_upload_messages(Path(__file__).resolve().parent)
        self.message_templates, self.event_templates = load_message_templates(Path(__file__).resolve().parent, self.upload_messages)
        self.sort_column: Optional[str] = None
        self.sort_reverse = False
        self.visible_record_indices: List[int] = []
        self.search_text = tk.StringVar()
        self.search_target = tk.StringVar(value="すべて")
        self.search_only = tk.BooleanVar(value=True)
        self.output_filter_mode = tk.StringVar(value="全表示")
        self.search_result_text = tk.StringVar(value="検索: 0件")
        self.search_match_indices: List[int] = []
        self.search_current_pos = -1
        self.upload_visible_indices: List[int] = []
        self.upload_search_text = tk.StringVar()
        self.upload_search_target = tk.StringVar(value="すべて")
        self.upload_search_only = tk.BooleanVar(value=True)
        self.upload_search_result_text = tk.StringVar(value="検索: 0件")
        self.upload_search_match_indices: List[int] = []
        self.upload_search_current_pos = -1
        self.session_loading = False
        self.session_ready = False
        self.session_save_after_id = None
        self.record_warnings_by_id: Dict[int, List[str]] = {}
        self.setup_ui()
        self.session_ready = True
        self.load_current_session()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def record_to_session(self, record: OrderRecord) -> Dict[str, object]:
        return {
            "source": dict(record.source),
            "invoice_type": record.invoice_type,
            "copies": record.copies,
            "delivery_date": record.delivery_date,
            "delivery_time": record.delivery_time,
            "selected": record.selected,
            "done": record.done,
            "bundle_id": record.bundle_id,
            "note": record.note,
            "row_id": record.row_id,
        }

    def record_from_session(self, data: Dict[str, object]) -> OrderRecord:
        source = data.get("source", {})
        if not isinstance(source, dict):
            source = {}
        try:
            copies = max(1, int(data.get("copies", 1) or 1))
        except Exception:
            copies = 1
        selected = bool(data.get("selected", True))
        if not clean(source.get("shipping_name", "")):
            selected = False
        return OrderRecord(
            source={str(k): str(v) for k, v in source.items()},
            invoice_type=clean(data.get("invoice_type", DEFAULT_INVOICE_CODE)) or DEFAULT_INVOICE_CODE,
            copies=copies,
            delivery_date=clean(data.get("delivery_date", "")),
            delivery_time=clean(data.get("delivery_time", "")),
            selected=selected,
            done=bool(data.get("done", False)),
            bundle_id=clean(data.get("bundle_id", "")),
            note=clean(data.get("note", "")),
            row_id=clean(data.get("row_id", "")),
        )

    def upload_record_to_session(self, rec: UploadRecord) -> Dict[str, object]:
        return {
            "order_id": rec.order_id(),
            "row_id": rec.order.row_id,
            "process_type": rec.process_type,
            "group_id": rec.group_id,
            "tracking_numbers": list(rec.tracking_numbers),
            "adopted_tracking": rec.adopted_tracking,
            "upload": rec.upload,
            "done": rec.done,
        }

    def upload_record_from_session(self, data: Dict[str, object], order_map: Dict[tuple, OrderRecord]) -> Optional[UploadRecord]:
        order_id = clean(data.get("order_id", ""))
        row_id = clean(data.get("row_id", ""))
        order = order_map.get((order_id, row_id)) or next(
            (record for (oid, _rid), record in order_map.items() if oid == order_id),
            None
        )
        if not order:
            return None
        tracking_numbers = data.get("tracking_numbers", [])
        if not isinstance(tracking_numbers, list):
            tracking_numbers = []
        return UploadRecord(
            order=order,
            process_type=clean(data.get("process_type", "通常")) or "通常",
            group_id=clean(data.get("group_id", "")),
            tracking_numbers=[clean(value) for value in tracking_numbers if clean(value)],
            adopted_tracking=clean(data.get("adopted_tracking", "")),
            upload=bool(data.get("upload", True)),
            done=bool(data.get("done", False)),
        )

    def save_current_session(self) -> None:
        if not self.session_ready or self.session_loading or not self.records:
            return
        data = {
            "csv_path": self.csv_path.get(),
            "ship_date": self.ship_date.get(),
            "encoding": self.encoding.get(),
            "group_candidates": self.group_candidates.get(),
            "split_b2_by_pdf": self.split_b2_by_pdf.get(),
            "split_pdf_pages": self.split_pdf_pages.get(),
            "sort_column": self.sort_column,
            "sort_reverse": self.sort_reverse,
            "bundle_counter": self.bundle_counter,
            "records": [self.record_to_session(record) for record in self.records],
            "upload_records": [self.upload_record_to_session(rec) for rec in self.upload_records],
            "upload_records_saved": True,
        }
        try:
            with session_path(Path(__file__).resolve().parent).open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def schedule_current_session_save(self) -> None:
        if not self.session_ready or self.session_loading or not self.records:
            return
        if self.session_save_after_id:
            self.root.after_cancel(self.session_save_after_id)
        self.session_save_after_id = self.root.after(1200, self.run_scheduled_session_save)

    def run_scheduled_session_save(self) -> None:
        self.session_save_after_id = None
        self.save_current_session()

    def load_current_session(self) -> None:
        path = session_path(Path(__file__).resolve().parent)
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            records_data = data.get("records", [])
            if not isinstance(records_data, list) or not records_data:
                return
            self.session_loading = True
            self.csv_path.set(str(data.get("csv_path", "")))
            self.encoding.set(str(data.get("encoding", self.encoding.get())))
            self.group_candidates.set(False)
            self.update_group_candidates_button()
            self.split_b2_by_pdf.set(bool(data.get("split_b2_by_pdf", False)))
            try:
                self.split_pdf_pages.set(max(1, int(data.get("split_pdf_pages", 1))))
            except Exception:
                self.split_pdf_pages.set(1)
            self.sort_column = data.get("sort_column") or None
            self.sort_reverse = bool(data.get("sort_reverse", False))
            self.bundle_counter = max(1, int(data.get("bundle_counter", 1) or 1))
            self.records = [self.record_from_session(item) for item in records_data if isinstance(item, dict)]
            self.refresh_tree()
            upload_records_data = data.get("upload_records", [])
            if data.get("upload_records_saved") and isinstance(upload_records_data, list):
                order_map = {(record.value("order_id"), record.row_id): record for record in self.records}
                restored_upload_records = [
                    self.upload_record_from_session(item, order_map)
                    for item in upload_records_data
                    if isinstance(item, dict)
                ]
                self.upload_records = [rec for rec in restored_upload_records if rec]
            else:
                self.initialize_upload_records()
                self.auto_classify_upload_records()
            self.refresh_upload_tree()
            self.status.set(f"前回保存した作業データを復元しました。{len(self.records)}件。")
        except Exception as e:
            self.status.set(f"前回作業データを読み込めませんでした: {e}")
        finally:
            self.session_loading = False

    def on_close(self) -> None:
        if self.session_save_after_id:
            self.root.after_cancel(self.session_save_after_id)
            self.session_save_after_id = None
        self.save_current_session()
        self.root.destroy()

    def delete_current_session_file(self) -> None:
        try:
            path = session_path(Path(__file__).resolve().parent)
            if path.exists():
                path.unlink()
        except Exception:
            pass

    def reset_ship_date_to_today(self) -> None:
        self.ship_date.set(datetime.now().strftime("%Y/%m/%d"))

    def clear_prep_list(self) -> None:
        if self.records and not messagebox.askyesno(APP_TITLE, "出荷準備と出荷後アップロードの一覧をすべてクリアしますか？"):
            return
        self.reset_ship_date_to_today()
        self.records = []
        self.upload_records = []
        self.csv_path.set("")
        self.search_text.set("")
        self.search_only.set(True)
        self.output_filter_mode.set("全表示")
        self.update_output_filter_button()
        self.upload_search_text.set("")
        self.upload_search_only.set(True)
        self.group_candidates.set(False)
        self.update_group_candidates_button()
        self.visible_record_indices = []
        self.upload_visible_indices = []
        self.last_warning_count = 0
        self.record_warnings_by_id = {}
        self.tree.delete(*self.tree.get_children())
        self.upload_tree.delete(*self.upload_tree.get_children())
        self.selected_count.set("0件選択")
        self.search_result_text.set("検索: 0件")
        self.upload_search_result_text.set("検索: 0件")
        self.status.set("一覧をクリアしました。")
        self.upload_status.set("出荷後アップロード一覧をクリアしました。")
        if self.session_save_after_id:
            self.root.after_cancel(self.session_save_after_id)
            self.session_save_after_id = None
        self.delete_current_session_file()

    def clear_upload_list(self) -> None:
        if self.upload_records and not messagebox.askyesno(APP_TITLE, "出荷後アップロードの一覧をクリアしますか？"):
            return
        self.reset_ship_date_to_today()
        self.upload_records = []
        self.upload_search_text.set("")
        self.upload_search_only.set(True)
        self.upload_visible_indices = []
        self.refresh_upload_tree()
        self.upload_status.set("出荷後アップロード一覧をクリアしました。")
        self.save_current_session()

    def save_pdf_font_settings(self, _event=None) -> None:
        try:
            font_size = max(18, min(48, int(self.pdf_font_size.get())))
        except Exception:
            font_size = 32
        font_name = self.pdf_font_name.get()
        if font_name not in PDF_FONT_OPTIONS:
            font_name = "メイリオ"
        self.pdf_font_size.set(str(font_size))
        self.pdf_font_name.set(font_name)
        self.app_settings["pdf_font_size"] = font_size
        self.app_settings["pdf_font_name"] = font_name
        save_app_settings(Path(__file__).resolve().parent, self.app_settings)

    def update_group_candidates_button(self) -> None:
        button = getattr(self, "group_candidates_button", None)
        if not button:
            return
        text = "同梱候補を解除" if self.group_candidates.get() else "同梱候補を集める"
        button.configure(text=text)

    def toggle_group_candidates(self) -> None:
        self.group_candidates.set(not self.group_candidates.get())
        self.update_group_candidates_button()
        self.apply_current_sort()

    def update_output_filter_button(self) -> None:
        button = getattr(self, "output_filter_button", None)
        if button:
            modes = ["全表示", "✓表示", "済表示"]
            current = self.output_filter_mode.get()
            try:
                next_mode = modes[(modes.index(current) + 1) % len(modes)]
            except ValueError:
                next_mode = modes[0]
            button.configure(text=next_mode)

    def toggle_output_filter_mode(self) -> None:
        modes = ["全表示", "✓表示", "済表示"]
        current = self.output_filter_mode.get()
        try:
            next_mode = modes[(modes.index(current) + 1) % len(modes)]
        except ValueError:
            next_mode = modes[0]
        self.output_filter_mode.set(next_mode)
        self.update_output_filter_button()
        self.refresh_tree(save_session=False)

    def load_postal_db(self) -> Optional[PostalCodeDatabase]:
        base_dir = Path(__file__).resolve().parent
        csv_path = base_dir / POSTAL_DATA_DIR / POSTAL_DATA_FILE
        if csv_path.exists():
            return PostalCodeDatabase(csv_path)
        return None

    def update_postal_database(self, parent: tk.Toplevel, status_var: tk.StringVar, url_var: tk.StringVar) -> None:
        download_url = clean(url_var.get()) or POSTAL_DATA_URL
        if not re.match(r"^https?://", download_url):
            messagebox.showwarning(APP_TITLE, "取得URLは http:// または https:// で始まるURLを入力してください。", parent=parent)
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"郵便番号DBをダウンロードして更新しますか？\n\n{download_url}",
            parent=parent,
        ):
            return
        base_dir = Path(__file__).resolve().parent
        postal_dir = base_dir / POSTAL_DATA_DIR
        postal_dir.mkdir(exist_ok=True)
        target_path = postal_dir / POSTAL_DATA_FILE
        stamp = datetime.now().strftime("%Y%m%d%H%M")
        backup_path = postal_dir / f"utf_ken_all_backup_{stamp}.csv"
        new_csv_path = postal_dir / f"utf_ken_all_new_{stamp}.csv"
        status_var.set("郵便番号DBをダウンロード中...")
        parent.update_idletasks()
        moved_backup = False
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = Path(temp_dir) / "utf_ken_all.zip"
                request = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=90) as response:
                    zip_path.write_bytes(response.read())
                with zipfile.ZipFile(zip_path) as zf:
                    csv_name = next(
                        (name for name in zf.namelist() if Path(name).name.lower() == POSTAL_DATA_FILE.lower()),
                        "",
                    )
                    if not csv_name:
                        raise RuntimeError(f"ZIP内に {POSTAL_DATA_FILE} が見つかりません。")
                    new_csv_path.write_bytes(zf.read(csv_name))
            test_db = PostalCodeDatabase(new_csv_path)
            if not test_db.loaded or len(test_db.by_zip) < 100000:
                raise RuntimeError(f"郵便番号DBの読込確認に失敗しました。件数: {len(test_db.by_zip):,}件")
            if target_path.exists():
                target_path.replace(backup_path)
                moved_backup = True
            new_csv_path.replace(target_path)
            self.postal_db = PostalCodeDatabase(target_path)
            self.app_settings["postal_data_url"] = download_url
            save_app_settings(Path(__file__).resolve().parent, self.app_settings)
            self.refresh_tree()
            status = self.postal_db.summary() if self.postal_db else "郵便番号DBなし"
            status_var.set(f"更新完了: {status}")
            if hasattr(self, "status"):
                self.status.set(status)
            messagebox.showinfo(
                APP_TITLE,
                f"郵便番号DBを更新しました。\n{status}\n\n旧DBバックアップ:\n{backup_path.name}",
                parent=parent,
            )
        except Exception as e:
            try:
                if new_csv_path.exists():
                    new_csv_path.unlink()
                if moved_backup and backup_path.exists() and not target_path.exists():
                    backup_path.replace(target_path)
            except Exception:
                pass
            status_var.set(f"更新失敗: {e}")
            messagebox.showerror(APP_TITLE, f"郵便番号DBを更新できませんでした。\n{e}", parent=parent)

    def setup_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        prep_tab = ttk.Frame(self.notebook)
        upload_tab = ttk.Frame(self.notebook)
        self.notebook.add(prep_tab, text="出荷準備")
        self.notebook.add(upload_tab, text="出荷後アップロード")

        top = ttk.Frame(prep_tab, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="受注CSV").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.csv_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(top, text="参照", command=self.select_csv).pack(side=tk.LEFT)
        ttk.Button(top, text="再読込", command=self.load_csv).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(top, text="出荷予定日").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.ship_date, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Label(top, text="CSV文字コード").pack(side=tk.LEFT)
        ttk.Combobox(top, textvariable=self.encoding, values=["Shift_JIS(cp932)", "UTF-8 BOM"], width=15, state="readonly").pack(side=tk.LEFT, padx=6)
        self.group_candidates_button = ttk.Button(top, text="同梱候補を集める", command=self.toggle_group_candidates)
        self.group_candidates_button.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(top, text="設定", command=self.open_invoice_type_settings).pack(side=tk.LEFT, padx=(12, 0))
        tk.Button(
            top,
            text="全クリア",
            command=self.clear_prep_list,
            bg="#ffd9a8",
            activebackground="#ffc987",
            fg="black",
            relief=tk.RAISED,
        ).pack(side=tk.LEFT, padx=(8, 0))

        search = ttk.Frame(prep_tab, padding=(8, 0, 8, 4))
        search.pack(fill=tk.X)
        ttk.Label(search, text="検索").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search, textvariable=self.search_text, width=32)
        self.search_entry.pack(side=tk.LEFT, padx=4)
        self.search_entry.bind("<Return>", self.apply_search_filter)
        ttk.Label(search, text="対象").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Combobox(
            search,
            textvariable=self.search_target,
            values=["すべて", "注文ID", "送付先", "注文者", "商品名", "住所", "郵便番号", "送り状種類", "同梱番号"],
            width=12,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="検索", command=self.apply_search_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="▶", width=3, command=self.select_next_search_match).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(search, text="クリア", command=self.clear_search_filter).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(search, text="検索結果のみ表示", variable=self.search_only, command=self.apply_search_filter).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Label(search, textvariable=self.search_result_text, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="表示行を選択", command=self.select_visible_rows).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(search, text="表示行を選択解除", command=self.clear_visible_selection).pack(side=tk.LEFT, padx=4)
        self.output_filter_button = ttk.Button(search, text="✓表示", command=self.toggle_output_filter_mode, width=8)
        self.output_filter_button.pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(search, text="表示行のみ選択", command=self.select_output_visible_only).pack(side=tk.LEFT, padx=4)

        columns = [
            ("warning", "確認", 58), ("selected", "出力", 48), ("order_id", "注文ID", 210),
            ("purchase_date", "購入日時", 132), ("shipping_name", "送付先", 125), ("shipping_state", "都道府県", 82),
            ("shipping_city", "市区町村", 130), ("shipping_postal_code", "郵便番号", 82),
            ("shipping_address_1", "町・番地", 170), ("shipping_address_2", "建物名等", 190),
            ("invoice_type", "送り状種類", 180), ("copies", "枚数", 52),
            ("product_name", "商品名", 560), ("quantity", "数量", 50), ("delivery_date", "お届け日", 88),
            ("delivery_time", "時間帯", 120),
        ]
        tree_frame = ttk.Frame(prep_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=[c[0] for c in columns], show="headings", selectmode="extended")
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.tag_configure("warning", foreground="red")
        self.tree.tag_configure("bundle", background="#fff4cc")
        self.tree.tag_configure("bundle_warning", background="#fff4cc", foreground="red")
        self.tree.tag_configure("manual_bundle", background="#dff0ff")
        self.tree.tag_configure("manual_bundle_warning", background="#dff0ff", foreground="red")
        self.tree.tag_configure("note", foreground="#005bbb")
        for key, label, width in columns:
            self.tree.heading(key, text=label, command=lambda k=key: self.sort_by(k))
            min_width = 300 if key == "product_name" else min(width, 90)
            self.tree.column(key, width=width, minwidth=min_width, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.begin_cell_edit)

        edit = ttk.LabelFrame(prep_tab, text="選択行の変更", padding=8)
        edit.pack(fill=tk.X, padx=8, pady=4)
        edit.columnconfigure(11, weight=1)
        self.selected_count = tk.StringVar(value="0件選択")
        ttk.Label(edit, textvariable=self.selected_count, width=12).grid(row=0, column=0, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="出力ON/OFF", command=self.toggle_selected, width=12).grid(row=0, column=1, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="同梱/解除", command=self.toggle_bundle_selected, width=12).grid(row=0, column=2, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="済", command=self.mark_selected_done, width=12).grid(row=1, column=1, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="済解除", command=self.clear_selected_done, width=12).grid(row=1, column=2, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="選択行を削除", command=self.delete_selected_orders, width=14).grid(row=1, column=0, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="送り状種類").grid(row=0, column=3, padx=(12, 4), pady=2, sticky="e")
        self.invoice_type_var = tk.StringVar(value=invoice_label(DEFAULT_INVOICE_CODE))
        self.invoice_type_combo = ttk.Combobox(edit, textvariable=self.invoice_type_var, values=INVOICE_TYPE_LABELS, width=28, state="readonly")
        self.invoice_type_combo.grid(row=0, column=4, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="お届け日").grid(row=0, column=5, padx=(12, 4), pady=2, sticky="e")
        self.delivery_date_var = tk.StringVar()
        ttk.Entry(edit, textvariable=self.delivery_date_var, width=12).grid(row=0, column=6, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="時間帯").grid(row=0, column=7, padx=(12, 4), pady=2, sticky="e")
        self.delivery_time_var = tk.StringVar(value="指定なし")
        ttk.Combobox(edit, textvariable=self.delivery_time_var, values=DELIVERY_TIME_LABELS, width=16, state="readonly").grid(row=0, column=8, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="送り状発行枚数").grid(row=1, column=3, padx=(12, 4), pady=2, sticky="e")
        self.copies_var = tk.IntVar(value=1)
        ttk.Spinbox(edit, from_=1, to=99, textvariable=self.copies_var, width=6).grid(row=1, column=4, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="出荷リスト文字").grid(row=1, column=5, padx=(12, 4), pady=2, sticky="e")
        self.pdf_font_size_combo = ttk.Combobox(edit, textvariable=self.pdf_font_size, values=PDF_FONT_SIZE_OPTIONS, width=6, state="readonly")
        self.pdf_font_size_combo.grid(row=1, column=6, padx=4, pady=2, sticky="w")
        self.pdf_font_size_combo.bind("<<ComboboxSelected>>", self.save_pdf_font_settings)
        ttk.Label(edit, text="フォント").grid(row=1, column=7, padx=(12, 4), pady=2, sticky="e")
        self.pdf_font_name_combo = ttk.Combobox(edit, textvariable=self.pdf_font_name, values=list(PDF_FONT_OPTIONS.keys()), width=14, state="readonly")
        self.pdf_font_name_combo.grid(row=1, column=8, padx=4, pady=2, sticky="w")
        self.pdf_font_name_combo.bind("<<ComboboxSelected>>", self.save_pdf_font_settings)
        apply_button = tk.Button(
            edit,
            text="適用",
            command=self.apply_selected_changes,
            font=("Yu Gothic UI", 16),
            relief=tk.RAISED,
            padx=12,
        )
        apply_button.grid(row=0, column=10, rowspan=2, padx=(16, 4), pady=2, sticky="ns")
        self.text_adjust_button = ttk.Button(edit, text="カーソル以降の文字を移動")
        self.text_adjust_button.grid(row=0, column=11, padx=4, pady=2, sticky="w")
        self.text_adjust_button.bind("<ButtonPress-1>", self.move_text_after_cursor)

        bottom = ttk.Frame(prep_tab, padding=8)
        bottom.pack(fill=tk.X)
        db_status = self.postal_db.summary() if self.postal_db else "郵便番号DBなし"
        self.status = tk.StringVar(value=f"CSVを読み込んでください。{db_status}")
        ttk.Label(bottom, textvariable=self.status).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(bottom, text="送り状CSV出力", command=self.export_csv).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="PDF出力", command=self.export_pdf).pack(side=tk.RIGHT, padx=4)
        tk.Button(
            bottom,
            text="CSV+PDF出力",
            command=self.export_both,
            bg="#c9f7d4",
            activebackground="#aef0bf",
            fg="black",
            relief=tk.RAISED,
            padx=10,
        ).pack(side=tk.RIGHT, padx=4)
        ttk.Combobox(bottom, textvariable=self.split_pdf_pages, values=[1, 2, 3, 4, 5], width=4, state="readonly").pack(side=tk.RIGHT, padx=(2, 4))
        ttk.Label(bottom, text="送り状データをPDF指定枚数ごとに出力").pack(side=tk.RIGHT, padx=(8, 2))
        ttk.Checkbutton(bottom, variable=self.split_b2_by_pdf).pack(side=tk.RIGHT, padx=(8, 2))
        self.setup_upload_tab(upload_tab)

    def select_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.csv_path.set(path)
            self.load_csv()

    def open_invoice_type_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("設定")
        win.geometry("1180x680")
        win.transient(self.root)
        settings = [dict(item) for item in INVOICE_TYPE_SETTINGS]
        sender_settings = dict(SENDER_SETTINGS)

        container = ttk.Frame(win, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        sender_frame = ttk.LabelFrame(container, text="出荷元設定", padding=8)
        sender_frame.grid(row=0, column=0, columnspan=9, sticky="ew", pady=(0, 8))
        sender_frame.columnconfigure(7, weight=1)
        sender_code_var = tk.StringVar(value=sender_settings.get("code", ""))
        sender_name_var = tk.StringVar(value=sender_settings.get("name", ""))
        sender_phone_var = tk.StringVar(value=sender_settings.get("phone", ""))
        sender_postal_var = tk.StringVar(value=sender_settings.get("postal_code", ""))
        sender_address_var = tk.StringVar(value=sender_settings.get("address", ""))
        sender_billing_var = tk.StringVar(value=sender_settings.get("billing_code", ""))
        sender_freight_var = tk.StringVar(value=sender_settings.get("freight_management_number", ""))
        default_item_var = tk.StringVar(value=sender_settings.get("default_item_name", DEFAULT_ITEM_NAME))

        ttk.Label(sender_frame, text="依頼主コード").grid(row=0, column=0, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_code_var, width=10).grid(row=0, column=1, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="依頼主名").grid(row=0, column=2, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_name_var, width=24).grid(row=0, column=3, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="電話番号").grid(row=0, column=4, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_phone_var, width=16).grid(row=0, column=5, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="郵便番号").grid(row=0, column=6, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_postal_var, width=12).grid(row=0, column=7, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="住所").grid(row=1, column=0, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_address_var).grid(row=1, column=1, columnspan=7, padx=4, pady=2, sticky="ew")
        ttk.Label(sender_frame, text="請求先顧客コード").grid(row=2, column=0, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_billing_var, width=18).grid(row=2, column=1, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="運賃管理番号").grid(row=2, column=2, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=sender_freight_var, width=10).grid(row=2, column=3, padx=4, pady=2, sticky="w")
        ttk.Label(sender_frame, text="既定品名").grid(row=2, column=4, padx=4, pady=2, sticky="e")
        ttk.Entry(sender_frame, textvariable=default_item_var, width=28).grid(row=2, column=5, columnspan=3, padx=4, pady=2, sticky="ew")
        postal_status_var = tk.StringVar(value=self.postal_db.summary() if self.postal_db else "郵便番号DBなし")
        postal_url_var = tk.StringVar(value=clean(self.app_settings.get("postal_data_url", "")) or POSTAL_DATA_URL)
        ttk.Label(sender_frame, textvariable=postal_status_var).grid(row=3, column=0, columnspan=2, padx=4, pady=(6, 2), sticky="w")
        ttk.Label(sender_frame, text="取得URL").grid(row=3, column=2, padx=4, pady=(6, 2), sticky="e")
        ttk.Entry(sender_frame, textvariable=postal_url_var).grid(row=3, column=3, columnspan=3, padx=4, pady=(6, 2), sticky="ew")

        def reset_postal_url():
            postal_url_var.set(POSTAL_DATA_URL)

        ttk.Button(sender_frame, text="既定に戻す", command=reset_postal_url).grid(row=3, column=6, padx=4, pady=(6, 2), sticky="e")
        ttk.Button(
            sender_frame,
            text="郵便番号DB更新",
            command=lambda: self.update_postal_database(win, postal_status_var, postal_url_var),
        ).grid(row=3, column=7, padx=4, pady=(6, 2), sticky="e")

        columns = [
            ("default", "既定", 60), ("carrier_id", "運送会社", 80), ("code", "コード", 80), ("name", "GUI表示名", 230),
            ("upload_name", "アップロード配送名", 240), ("input_keywords", "受注CSV発送方法", 220),
            ("item_name", "品名1", 180), ("cool_type", "クール", 70),
        ]
        tree = ttk.Treeview(container, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, minwidth=min(width, 100), stretch=False)
        tree.grid(row=1, column=0, columnspan=8, sticky="nsew")
        y_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)
        y_scroll.grid(row=1, column=8, sticky="ns")

        code_var = tk.StringVar()
        carrier_id_var = tk.StringVar(value="yamato")
        name_var = tk.StringVar()
        upload_name_var = tk.StringVar()
        keywords_var = tk.StringVar()
        item_name_var = tk.StringVar()
        cool_type_var = tk.StringVar()
        handling1_var = tk.StringVar()
        handling2_var = tk.StringVar()
        article_var = tk.StringVar()
        ehiden_speed_var = tk.StringVar()
        ehiden_cool_var = tk.StringVar()
        ehiden_package_var = tk.StringVar()
        ehiden_mototyaku_var = tk.StringVar()
        default_var = tk.BooleanVar(value=False)

        def refresh():
            tree.delete(*tree.get_children())
            for idx, item in enumerate(settings):
                tree.insert("", tk.END, iid=str(idx), values=(
                    "✓" if item.get("default") else "",
                    item.get("carrier_id", "yamato"),
                    item.get("code", ""),
                    item.get("name", ""),
                    item.get("upload_name", ""),
                    item.get("input_keywords", ""),
                    item.get("item_name", ""),
                    item.get("cool_type", ""),
                ))

        def load_selection(_event=None):
            selection = tree.selection()
            if not selection:
                return
            item = settings[int(selection[0])]
            carrier_id_var.set(str(item.get("carrier_id", "yamato")))
            code_var.set(str(item.get("code", "")))
            name_var.set(str(item.get("name", "")))
            upload_name_var.set(str(item.get("upload_name", "")))
            keywords_var.set(str(item.get("input_keywords", "")))
            item_name_var.set(str(item.get("item_name", "")))
            cool_type_var.set(str(item.get("cool_type", "")))
            handling1_var.set(str(item.get("handling1", "")))
            handling2_var.set(str(item.get("handling2", "")))
            article_var.set(str(item.get("article", "")))
            ehiden_speed_var.set(str(item.get("ehiden_speed_code", "")))
            ehiden_cool_var.set(str(item.get("ehiden_cool_code", "")))
            ehiden_package_var.set(str(item.get("ehiden_package_code", "")))
            ehiden_mototyaku_var.set(str(item.get("ehiden_mototyaku_type", "")))
            default_var.set(bool(item.get("default", False)))

        def apply_row():
            code = clean(code_var.get())
            name = clean(name_var.get())
            if not code or not name:
                messagebox.showwarning(APP_TITLE, "コードとGUI表示名は必須です。", parent=win)
                return
            selection = tree.selection()
            idx = int(selection[0]) if selection else None
            if any(clean(item.get("code", "")) == code and i != idx for i, item in enumerate(settings)):
                messagebox.showwarning(APP_TITLE, "同じコードがすでに存在します。", parent=win)
                return
            item = {
                "code": code,
                "name": name,
                "upload_name": clean(upload_name_var.get()) or f"ヤマト運輸({code})",
                "input_keywords": clean(keywords_var.get()),
                "item_name": clean(item_name_var.get()),
                "cool_type": clean(cool_type_var.get()),
                "handling1": clean(handling1_var.get()),
                "handling2": clean(handling2_var.get()),
                "article": clean(article_var.get()),
                "carrier_id": clean(carrier_id_var.get()) or "yamato",
                "ehiden_speed_code": clean(ehiden_speed_var.get()),
                "ehiden_cool_code": clean(ehiden_cool_var.get()),
                "ehiden_package_code": clean(ehiden_package_var.get()),
                "ehiden_mototyaku_type": clean(ehiden_mototyaku_var.get()),
                "default": bool(default_var.get()),
            }
            if item["default"]:
                for other in settings:
                    other["default"] = False
            if idx is None:
                settings.append(item)
            else:
                settings[idx] = item
            refresh()
            tree.selection_set(str(idx if idx is not None else len(settings) - 1))

        def add_row():
            tree.selection_remove(tree.selection())
            carrier_id_var.set("yamato")
            code_var.set("")
            name_var.set("")
            upload_name_var.set("")
            keywords_var.set("")
            item_name_var.set("")
            cool_type_var.set("")
            handling1_var.set("")
            handling2_var.set("")
            article_var.set("")
            ehiden_speed_var.set("")
            ehiden_cool_var.set("")
            ehiden_package_var.set("")
            ehiden_mototyaku_var.set("")
            default_var.set(False)

        def delete_row():
            selection = tree.selection()
            if not selection:
                return
            idx = int(selection[0])
            code = clean(settings[idx].get("code", ""))
            if any(record.invoice_type == code for record in self.records):
                messagebox.showwarning(APP_TITLE, "現在の一覧で使用中の送り状種類は削除できません。", parent=win)
                return
            settings.pop(idx)
            if settings and not any(item.get("default") for item in settings):
                settings[0]["default"] = True
            refresh()

        def save():
            normalized = normalize_invoice_settings(settings)
            sender = normalize_sender_settings({
                "code": sender_code_var.get(),
                "name": sender_name_var.get(),
                "phone": sender_phone_var.get(),
                "postal_code": sender_postal_var.get(),
                "address": sender_address_var.get(),
                "billing_code": sender_billing_var.get(),
                "freight_management_number": sender_freight_var.get(),
                "default_item_name": default_item_var.get(),
            })
            apply_sender_settings(sender)
            save_invoice_settings(Path(__file__).resolve().parent, normalized, sender)
            apply_invoice_settings(normalized)
            ensure_upload_message_methods(self.upload_messages)
            save_upload_messages(Path(__file__).resolve().parent, self.upload_messages)
            self.app_settings["postal_data_url"] = clean(postal_url_var.get()) or POSTAL_DATA_URL
            save_app_settings(Path(__file__).resolve().parent, self.app_settings)
            existing_template_codes = {clean(row.get("invoice_code", "")) for row in self.message_templates}
            for row in default_method_template_rows(self.upload_messages):
                if row["invoice_code"] not in existing_template_codes:
                    self.message_templates.append(row)
            save_message_templates(Path(__file__).resolve().parent, self.message_templates, self.event_templates)
            if hasattr(self, "invoice_type_combo"):
                self.invoice_type_combo.configure(values=INVOICE_TYPE_LABELS)
                if invoice_code(self.invoice_type_var.get()) not in INVOICE_TYPE_NAMES:
                    self.invoice_type_var.set(invoice_label(DEFAULT_INVOICE_CODE))
            self.refresh_tree()
            self.refresh_upload_tree()
            win.destroy()
            messagebox.showinfo(APP_TITLE, "設定を保存しました。")

        edit = ttk.LabelFrame(container, text="送り状種類 / B2出力設定", padding=8)
        edit.grid(row=2, column=0, columnspan=9, sticky="ew", pady=(10, 0))
        edit.columnconfigure(7, weight=1)
        ttk.Checkbutton(edit, text="既定", variable=default_var).grid(row=0, column=0, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="運送会社").grid(row=0, column=1, padx=4, pady=2, sticky="e")
        ttk.Combobox(edit, textvariable=carrier_id_var, values=["yamato", "sagawa"], width=10, state="readonly").grid(row=0, column=2, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="コード").grid(row=0, column=3, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=code_var, width=8).grid(row=0, column=4, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="GUI表示名").grid(row=0, column=5, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=name_var, width=28).grid(row=0, column=6, columnspan=2, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="アップロード配送名").grid(row=1, column=1, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=upload_name_var, width=38).grid(row=1, column=2, columnspan=3, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="受注CSV発送方法").grid(row=1, column=5, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=keywords_var).grid(row=1, column=6, columnspan=2, padx=4, pady=2, sticky="ew")
        ttk.Label(edit, text="品名1").grid(row=2, column=1, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=item_name_var, width=38).grid(row=2, column=2, columnspan=3, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="クール区分").grid(row=2, column=5, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=cool_type_var, width=10).grid(row=2, column=6, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="荷扱い1").grid(row=3, column=1, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=handling1_var, width=20).grid(row=3, column=2, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="荷扱い2").grid(row=3, column=3, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=handling2_var, width=20).grid(row=3, column=4, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="記事").grid(row=3, column=5, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=article_var).grid(row=3, column=6, columnspan=2, padx=4, pady=2, sticky="ew")
        ttk.Label(edit, text="佐川 荷姿").grid(row=4, column=1, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=ehiden_package_var, width=8).grid(row=4, column=2, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="スピード").grid(row=4, column=3, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=ehiden_speed_var, width=8).grid(row=4, column=4, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="クール").grid(row=4, column=5, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=ehiden_cool_var, width=8).grid(row=4, column=6, padx=4, pady=2, sticky="w")
        ttk.Label(edit, text="元着").grid(row=4, column=7, padx=4, pady=2, sticky="e")
        ttk.Entry(edit, textvariable=ehiden_mototyaku_var, width=8).grid(row=4, column=8, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="行へ反映", command=apply_row).grid(row=0, column=8, padx=4, pady=2)
        ttk.Button(edit, text="追加", command=add_row).grid(row=1, column=8, padx=4, pady=2)
        ttk.Button(edit, text="削除", command=delete_row).grid(row=2, column=8, padx=4, pady=2)

        bottom = ttk.Frame(container)
        bottom.grid(row=3, column=0, columnspan=9, sticky="e", pady=(10, 0))
        ttk.Label(bottom, text="受注CSV発送方法は複数指定できます。例: 宅配便,クール便").pack(side=tk.LEFT, padx=(0, 16))
        ttk.Button(bottom, text="テンプレート設定", command=self.open_template_settings).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="保存", command=save).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="閉じる", command=win.destroy).pack(side=tk.LEFT, padx=4)

        tree.bind("<<TreeviewSelect>>", load_selection)
        refresh()
        if settings:
            tree.selection_set("0")
            load_selection()

    def setup_upload_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, padding=8)
        top.pack(fill=tk.X)
        ttk.Button(top, text="出荷データ読込", command=self.load_b2_result_csv).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="メッセージ設定", command=self.open_upload_message_settings).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="選択荷物番号を採用して同梱", command=self.adopt_tracking_for_selected).pack(side=tk.LEFT, padx=(16, 4))
        tk.Button(
            top,
            text="全クリア",
            command=self.clear_upload_list,
            bg="#ffd9a8",
            activebackground="#ffc987",
            fg="black",
            relief=tk.RAISED,
        ).pack(side=tk.LEFT, padx=(16, 4))

        search = ttk.Frame(parent, padding=(8, 0, 8, 4))
        search.pack(fill=tk.X)
        ttk.Label(search, text="検索").pack(side=tk.LEFT)
        self.upload_search_entry = ttk.Entry(search, textvariable=self.upload_search_text, width=32)
        self.upload_search_entry.pack(side=tk.LEFT, padx=4)
        self.upload_search_entry.bind("<Return>", self.apply_upload_search_filter)
        ttk.Label(search, text="対象").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Combobox(
            search,
            textvariable=self.upload_search_target,
            values=["すべて", "判定", "グループ", "注文ID", "送付先", "注文者", "商品名", "送り状", "荷物番号", "採用荷物番号", "出力"],
            width=14,
            state="readonly",
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="検索", command=self.apply_upload_search_filter).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="▶", width=3, command=self.select_next_upload_search_match).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(search, text="クリア", command=self.clear_upload_search_filter).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(search, text="検索結果のみ表示", variable=self.upload_search_only, command=self.apply_upload_search_filter).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Label(search, textvariable=self.upload_search_result_text, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(search, text="表示行を選択", command=self.select_visible_upload_rows).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(search, text="表示行を選択解除", command=self.clear_visible_upload_selection).pack(side=tk.LEFT, padx=4)

        columns = [
            ("upload", "出力", 48), ("status", "判定", 90), ("group_id", "グループ", 80),
            ("order_id", "注文ID", 220), ("shipping_name", "送付先", 130), ("buyer_name", "注文者", 130),
            ("product_name", "商品名", 420), ("quantity", "数量", 55), ("invoice_type", "送り状", 150),
            ("tracking", "荷物番号", 210), ("adopted", "採用荷物番号", 160),
        ]
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.upload_tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", selectmode="extended")
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.upload_tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.upload_tree.xview)
        self.upload_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        for key, label, width in columns:
            self.upload_tree.heading(key, text=label)
            self.upload_tree.column(key, width=width, minwidth=min(width, 100), stretch=False)
        self.upload_tree.tag_configure("normal", background="white")
        self.upload_tree.tag_configure("combined", background="#fff4cc")
        self.upload_tree.tag_configure("split", background="#dff0ff")
        self.upload_tree.tag_configure("excluded", background="#e5e5e5")
        self.upload_tree.tag_configure("done", background="#eeeeee", foreground="#777777")
        self.upload_tree.tag_configure("warning", background="#ffd6d6")
        self.upload_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.upload_tree.bind("<Double-1>", self.begin_upload_cell_edit)

        edit = ttk.LabelFrame(parent, text="選択行の変更", padding=8)
        edit.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(edit, text="出力ON/OFF", command=self.toggle_selected_upload_output, width=12).grid(row=0, column=1, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="同梱にする", command=lambda: self.set_upload_process_type("同梱"), width=12).grid(row=0, column=2, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="済", command=self.mark_selected_upload_done, width=12).grid(row=1, column=1, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="済解除", command=self.clear_selected_upload_done, width=12).grid(row=1, column=2, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="分割にする", command=lambda: self.set_upload_process_type("分割"), width=12).grid(row=0, column=3, padx=(12, 4), pady=2, sticky="w")
        ttk.Button(edit, text="通常に戻す", command=lambda: self.set_upload_process_type("通常"), width=12).grid(row=0, column=4, padx=4, pady=2, sticky="w")
        ttk.Button(edit, text="対象外", command=self.exclude_upload_selected, width=12).grid(row=1, column=3, padx=(12, 4), pady=2, sticky="w")

        bottom = ttk.Frame(parent, padding=8)
        bottom.pack(fill=tk.X)
        self.upload_status = tk.StringVar(value="受注CSVを読み込み、B2出荷データを取り込んでください。")
        ttk.Label(bottom, textvariable=self.upload_status).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(
            bottom,
            text="メルカリアップロードCSV出力",
            command=self.export_mercari_upload_csv,
            bg="#c9f7d4",
            activebackground="#aef0bf",
            fg="black",
            relief=tk.RAISED,
            padx=10,
        ).pack(side=tk.RIGHT, padx=4)

    def initialize_upload_records(self) -> None:
        self.upload_records = [UploadRecord(order=record) for record in self.records]
        self.upload_group_counter = 1

    def sync_upload_records_with_orders(self) -> None:
        existing_by_order_object = {id(rec.order): rec for rec in self.upload_records}
        unused_by_order_id: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            unused_by_order_id.setdefault(rec.order_id(), []).append(rec)
        synced = []
        used_upload_ids = set()
        for record in self.records:
            upload_rec = existing_by_order_object.get(id(record))
            if not upload_rec:
                candidates = unused_by_order_id.get(record.value("order_id"), [])
                upload_rec = next((candidate for candidate in candidates if id(candidate) not in used_upload_ids), None)
            if upload_rec:
                upload_rec.order = record
                used_upload_ids.add(id(upload_rec))
                synced.append(upload_rec)
            else:
                synced.append(UploadRecord(order=record))
        self.upload_records = synced
        if not self.upload_group_counter:
            self.upload_group_counter = 1

    def upload_searchable_texts(self, rec: UploadRecord) -> Dict[str, str]:
        values = {
            "判定": rec.process_type,
            "グループ": rec.group_id,
            "注文ID": rec.order_id(),
            "送付先": rec.order.value("shipping_name"),
            "注文者": rec.order.value("buyer_name"),
            "商品名": rec.order.value("product_name"),
            "送り状": invoice_label(rec.order.invoice_type),
            "荷物番号": rec.tracking_text(),
            "採用荷物番号": rec.adopted_tracking,
            "出力": "済" if rec.done else ("出力" if rec.upload else "対象外"),
        }
        values["すべて"] = " ".join(values.values())
        return values

    def matches_upload_search(self, rec: UploadRecord) -> bool:
        text = self.upload_search_text.get().strip().lower()
        if not text:
            return True
        target = self.upload_search_target.get()
        values = self.upload_searchable_texts(rec)
        haystack = values.get(target, values["すべて"]).lower()
        return all(word in haystack for word in text.split())

    def apply_upload_search_filter(self, _event=None) -> None:
        self.upload_search_current_pos = -1
        self.refresh_upload_tree(save_session=False)

    def clear_upload_search_filter(self) -> None:
        self.upload_search_text.set("")
        self.upload_search_only.set(True)
        self.upload_search_current_pos = -1
        self.refresh_upload_tree(save_session=False)

    def update_upload_search_result_text(self) -> None:
        if self.upload_search_text.get().strip():
            total = len(self.upload_search_match_indices)
            if total and self.upload_search_current_pos >= 0:
                self.upload_search_result_text.set(f"検索: {self.upload_search_current_pos + 1}/{total}件")
            else:
                self.upload_search_result_text.set(f"検索: {total}件")
        else:
            self.upload_search_result_text.set(f"表示: {len(self.upload_records)}件")

    def select_next_upload_search_match(self) -> None:
        if not self.upload_search_text.get().strip():
            return
        if not self.upload_search_match_indices:
            self.refresh_upload_tree(save_session=False)
        if not self.upload_search_match_indices:
            return
        self.upload_search_current_pos = (self.upload_search_current_pos + 1) % len(self.upload_search_match_indices)
        idx = self.upload_search_match_indices[self.upload_search_current_pos]
        iid = str(idx)
        if self.upload_tree.exists(iid):
            self.upload_tree.selection_set(iid)
            self.upload_tree.focus(iid)
            self.upload_tree.see(iid)
        self.update_upload_search_result_text()

    def select_visible_upload_rows(self) -> None:
        visible = [str(idx) for idx in self.upload_visible_indices]
        self.upload_tree.selection_set(visible)

    def clear_visible_upload_selection(self) -> None:
        visible = [str(idx) for idx in self.upload_visible_indices]
        self.upload_tree.selection_remove(visible)

    def refresh_upload_tree(self, save_session: bool = True) -> None:
        if not hasattr(self, "upload_tree"):
            return
        self.upload_tree.delete(*self.upload_tree.get_children())
        has_search = bool(self.upload_search_text.get().strip())
        matches = [self.matches_upload_search(rec) for rec in self.upload_records]
        self.upload_search_match_indices = [idx for idx, matched in enumerate(matches) if has_search and matched]
        if self.upload_search_current_pos >= len(self.upload_search_match_indices):
            self.upload_search_current_pos = -1
        self.update_upload_search_result_text()
        self.upload_visible_indices = []
        for idx, rec in enumerate(self.upload_records):
            if self.upload_search_only.get() and not matches[idx]:
                continue
            self.upload_visible_indices.append(idx)
            if rec.done:
                tag = "done"
            elif not rec.upload:
                tag = "excluded"
            elif rec.process_type == "同梱":
                tag = "combined"
            elif rec.process_type == "分割":
                tag = "split"
            elif not rec.adopted_tracking and not rec.tracking_numbers:
                tag = "warning"
            else:
                tag = "normal"
            self.upload_tree.insert("", tk.END, iid=str(idx), values=(
                "済" if rec.done else ("✓" if rec.upload else ""),
                rec.process_type,
                rec.group_id,
                rec.order_id(),
                rec.order.value("shipping_name"),
                rec.order.value("buyer_name"),
                gui_preview(rec.order.value("product_name"), 120),
                rec.order.value("quantity"),
                invoice_label(rec.order.invoice_type),
                gui_preview(rec.tracking_text(), 80),
                gui_preview(rec.adopted_tracking, 80),
            ), tags=(tag,))
        if save_session:
            self.schedule_current_session_save()

    def selected_upload_records(self) -> List[UploadRecord]:
        if not hasattr(self, "upload_tree"):
            return []
        return [self.upload_records[int(iid)] for iid in self.upload_tree.selection()]

    def toggle_selected_upload_output(self) -> None:
        selected = self.selected_upload_records()
        if not selected:
            messagebox.showwarning(APP_TITLE, "出力ON/OFFを変更する行を選択してください。")
            return
        for rec in selected:
            if rec.done:
                continue
            rec.upload = not rec.upload
            if rec.upload and rec.process_type == "除外":
                rec.process_type = "通常"
        self.refresh_upload_tree()

    def mark_selected_upload_done(self) -> None:
        selected = self.selected_upload_records()
        if not selected:
            messagebox.showwarning(APP_TITLE, "済にする行を選択してください。")
            return
        for rec in selected:
            rec.done = True
        self.refresh_upload_tree()

    def clear_selected_upload_done(self) -> None:
        selected = self.selected_upload_records()
        if not selected:
            messagebox.showwarning(APP_TITLE, "済解除する行を選択してください。")
            return
        for rec in selected:
            rec.done = False
        self.refresh_upload_tree()

    def sync_upload_order_to_records(self) -> None:
        if not self.upload_records:
            return
        by_record_id = {id(rec.order): rec for rec in self.upload_records}
        ordered = []
        for record in self.records:
            rec = by_record_id.get(id(record))
            if rec:
                ordered.append(rec)
        existing_ids = {id(rec.order) for rec in ordered}
        ordered.extend([rec for rec in self.upload_records if id(rec.order) not in existing_ids])
        self.upload_records = ordered
        self.refresh_upload_tree()

    def begin_upload_cell_edit(self, event) -> None:
        row_id = self.upload_tree.identify_row(event.y)
        column_id = self.upload_tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        column_index = int(column_id.replace("#", "")) - 1
        columns = list(self.upload_tree["columns"])
        if column_index < 0 or column_index >= len(columns):
            return
        key = columns[column_index]
        rec = self.upload_records[int(row_id)]

        if key == "upload":
            if rec.done:
                return
            rec.upload = not rec.upload
            if rec.upload and rec.process_type == "除外":
                rec.process_type = "通常"
            self.refresh_upload_tree()
            return
        if key not in {"tracking", "adopted"}:
            return

        bbox = self.upload_tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, width, height = bbox
        current = rec.tracking_text() if key == "tracking" else rec.adopted_tracking
        widget = ttk.Entry(self.upload_tree)
        widget.insert(0, current)
        widget.place(x=x, y=y, width=width, height=height)
        widget.focus_set()
        widget.selection_range(0, tk.END)
        closed = {"done": False}

        def commit(_event=None):
            if closed["done"]:
                return
            closed["done"] = True
            value = widget.get().strip()
            if key == "tracking":
                numbers = [clean(part) for part in re.split(r"[\s,，/／]+", value) if clean(part)]
                rec.tracking_numbers = numbers
                if len(numbers) > 1:
                    rec.process_type = "分割"
                    rec.adopted_tracking = joined_tracking_numbers(numbers)
                elif numbers and (not rec.adopted_tracking or rec.adopted_tracking not in numbers):
                    rec.adopted_tracking = numbers[0]
                elif not numbers:
                    rec.adopted_tracking = ""
            else:
                numbers = [clean(part) for part in re.split(r"[\s,，/／]+", value) if clean(part)]
                if rec.process_type == "分割" and numbers:
                    rec.tracking_numbers = numbers
                    rec.adopted_tracking = joined_tracking_numbers(numbers)
                else:
                    rec.adopted_tracking = value
                    if value and value not in rec.tracking_numbers:
                        rec.tracking_numbers.append(value)
            widget.destroy()
            self.refresh_upload_tree()

        def cancel(_event=None):
            closed["done"] = True
            widget.destroy()

        widget.bind("<Return>", commit)
        widget.bind("<FocusOut>", commit)
        widget.bind("<Escape>", cancel)

    def load_b2_result_csv(self) -> None:
        if not self.records:
            messagebox.showwarning(APP_TITLE, "先に出荷準備タブで受注CSVを読み込んでください。")
            return
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows = read_b2_result_rows(Path(path))
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        check = self.apply_b2_rows_to_upload_records(rows)
        if check.get("cancelled"):
            return
        self.auto_classify_upload_records()
        check.update(self.upload_tracking_summary(check))
        self.refresh_upload_tree()
        messages = [
            f"荷物番号を{check['tracking_numbers_imported']}件取り込みました。"
            f"うち{check['split_tracking_numbers']}件は分割発送のため"
            f"{check['direct_tracking_reflected_orders']}件への反映となります。"
        ]
        if check.get("added_tracking_numbers") is not None:
            messages.append(f"追加された荷物番号: {check['added_tracking_numbers']}件")
        if check.get("replaced_tracking_orders"):
            messages.append(f"既存番号を入れ替えた注文: {check['replaced_tracking_orders']}件")
        messages.append(
            f"荷物番号未登録の注文: {check['missing_tracking_orders']}件。"
            f"うち{check['assigned_by_combined']}件は同梱処理のため番号の割り当て済み"
        )
        messages.append(f"合計{check['assigned_orders']}件の注文に番号が割り当てられました。")
        if check["unmatched_b2_rows"]:
            messages.append(f"受注CSVにないB2行: {check['unmatched_b2_rows']}件")
        if check["duplicate_order_ids"]:
            messages.append(f"受注CSV内の重複注文ID: {check['duplicate_order_ids']}件")
        self.upload_status.set("\n".join(messages))
        if check["unmatched_b2_rows"]:
            messagebox.showwarning(
                APP_TITLE,
                "B2出荷データに、現在の受注CSVに存在しない注文IDが含まれています。\n"
                "CSVの取り違えがないか確認してください。"
            )

    def apply_b2_rows_to_upload_records(self, rows: List[List[str]]) -> Dict[str, int]:
        if not self.upload_records:
            self.initialize_upload_records()
        by_order_id: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            by_order_id.setdefault(rec.order_id(), []).append(rec)
        by_manage_no: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            by_manage_no.setdefault(ehiden_manage_no(rec.order), []).append(rec)
        import_items = []
        unmatched_b2_rows = 0
        tracking_numbers_imported = 0
        for row in rows:
            order_id = clean(row[0])
            matched_records = by_order_id.get(order_id, [])
            is_sagawa_row = False
            if not matched_records and len(row) > 18:
                manage_no = clean(row[18])
                matched_records = by_manage_no.get(manage_no, [])
                is_sagawa_row = bool(matched_records)
            if not matched_records:
                unmatched_b2_rows += 1
                continue
            code = "" if is_sagawa_row else clean(row[1])
            tracking = clean(row[0]) if is_sagawa_row else (clean(row[3]) if len(row) > 3 else "")
            ship_date = clean(row[2]) if is_sagawa_row and len(row) > 2 else (clean(row[4]) if len(row) > 4 else "")
            if tracking:
                tracking_numbers_imported += 1
            import_items.append((matched_records, code, tracking, ship_date))
        conflict_records = []
        for matched_records, _code, tracking, _ship_date in import_items:
            if not tracking:
                continue
            for rec in matched_records:
                existing = [number for number in rec.tracking_numbers if number]
                if existing and tracking not in existing:
                    conflict_records.append(rec)
        conflict_mode = "add"
        if conflict_records:
            result = messagebox.askyesnocancel(
                APP_TITLE,
                "既に荷物番号が入っている注文に、別の荷物番号が読み込まれました。\n\n"
                "「はい」: 既存番号を残して追加します。分割発送候補になります。\n"
                "「いいえ」: 対象注文の既存番号を消して、今回の番号に入れ替えます。\n"
                "「キャンセル」: 読み込みを中止します。",
            )
            if result is None:
                return {
                    "cancelled": 1,
                    "unmatched_b2_rows": unmatched_b2_rows,
                    "missing_tracking_orders": 0,
                    "duplicate_order_ids": 0,
                    "tracking_numbers_imported": 0,
                }
            conflict_mode = "add" if result else "replace"
        replaced_records = set()
        added_tracking_numbers = 0
        for matched_records, code, tracking, ship_date in import_items:
            for rec in matched_records:
                rec.upload = True
                if conflict_mode == "replace" and tracking and rec.tracking_numbers and tracking not in rec.tracking_numbers and id(rec) not in replaced_records:
                    rec.tracking_numbers = []
                    rec.adopted_tracking = ""
                    replaced_records.add(id(rec))
                if code:
                    rec.order.invoice_type = code
                if ship_date:
                    rec.order.delivery_date = ship_date
                if tracking and tracking not in rec.tracking_numbers:
                    rec.tracking_numbers.append(tracking)
                    added_tracking_numbers += 1
                if not rec.adopted_tracking and tracking:
                    rec.adopted_tracking = tracking
        duplicate_order_ids = sum(1 for records in by_order_id.values() if len(records) > 1)
        missing_tracking_orders = sum(1 for rec in self.upload_records if not rec.tracking_numbers and rec.upload)
        return {
            "unmatched_b2_rows": unmatched_b2_rows,
            "missing_tracking_orders": missing_tracking_orders,
            "duplicate_order_ids": duplicate_order_ids,
            "tracking_numbers_imported": tracking_numbers_imported,
            "added_tracking_numbers": added_tracking_numbers,
            "replaced_tracking_orders": len(replaced_records),
        }

    def upload_record_has_tracking(self, rec: UploadRecord, group_records: Optional[List[UploadRecord]] = None) -> bool:
        if rec.adopted_tracking or rec.tracking_numbers:
            return True
        if group_records:
            return any(group_rec.adopted_tracking or group_rec.tracking_numbers for group_rec in group_records)
        return False

    def sync_upload_adopted_tracking(self, rec: UploadRecord) -> None:
        if rec.process_type == "分割":
            rec.adopted_tracking = joined_tracking_numbers(rec.tracking_numbers) or rec.adopted_tracking
        elif rec.tracking_numbers and (
            not rec.adopted_tracking or rec.adopted_tracking not in rec.tracking_numbers
        ):
            rec.adopted_tracking = rec.tracking_numbers[0]

    def choose_tracking_number(self, title: str, message: str, numbers: List[str]) -> str:
        numbers = [clean(number) for number in numbers if clean(number)]
        if not numbers:
            return ""
        if len(numbers) == 1:
            return numbers[0]
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("420x150")
        win.transient(self.root)
        win.grab_set()
        selected = tk.StringVar(value=numbers[0])
        result = {"value": ""}
        ttk.Label(win, text=message).pack(padx=12, pady=(14, 8), anchor="w")
        combo = ttk.Combobox(win, textvariable=selected, values=numbers, state="readonly", width=36)
        combo.pack(padx=12, pady=4, fill=tk.X)
        combo.focus_set()

        def apply():
            result["value"] = clean(selected.get())
            win.destroy()

        def cancel():
            win.destroy()

        buttons = ttk.Frame(win)
        buttons.pack(pady=10)
        ttk.Button(buttons, text="採用", command=apply).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="キャンセル", command=cancel).pack(side=tk.LEFT, padx=4)
        self.root.wait_window(win)
        return result["value"]

    def upload_tracking_summary(self, check: Dict[str, int]) -> Dict[str, int]:
        group_map: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            if rec.group_id:
                group_map.setdefault(rec.group_id, []).append(rec)
        direct_tracking_reflected_orders = sum(1 for rec in self.upload_records if rec.tracking_numbers)
        split_tracking_numbers = sum(
            len(rec.tracking_numbers)
            for rec in self.upload_records
            if rec.process_type == "分割" and len(rec.tracking_numbers) > 1
        )
        missing_before_combined = check.get("missing_tracking_orders", 0)
        assigned_by_combined = sum(
            1
            for rec in self.upload_records
            if rec.upload
            and not rec.tracking_numbers
            and rec.process_type == "同梱"
            and self.upload_record_has_tracking(rec, group_map.get(rec.group_id, [rec]))
        )
        assigned_orders = sum(
            1
            for rec in self.upload_records
            if rec.upload and self.upload_record_has_tracking(rec, group_map.get(rec.group_id, [rec]))
        )
        return {
            "direct_tracking_reflected_orders": direct_tracking_reflected_orders,
            "split_tracking_numbers": split_tracking_numbers,
            "missing_tracking_orders": missing_before_combined,
            "assigned_by_combined": assigned_by_combined,
            "assigned_orders": assigned_orders,
        }

    def auto_classify_upload_records(self) -> None:
        group_index = 1
        manual_groups: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            if rec.done:
                continue
            if rec.order.bundle_id:
                manual_groups.setdefault(rec.order.bundle_id, []).append(rec)
        for bundle_id, records in manual_groups.items():
            if len(records) < 2:
                continue
            trackings = sorted({t for rec in records for t in rec.tracking_numbers if t})
            adopted = trackings[0] if trackings else ""
            for rec in records:
                rec.process_type = "同梱"
                rec.group_id = bundle_id
                if adopted:
                    rec.adopted_tracking = adopted

        for rec in self.upload_records:
            if rec.order.bundle_id:
                continue
            if rec.done:
                continue
            if len(rec.tracking_numbers) > 1:
                rec.process_type = "分割"
                rec.group_id = f"S{group_index}"
                self.sync_upload_adopted_tracking(rec)
                group_index += 1
        address_groups: Dict[tuple, List[UploadRecord]] = {}
        for rec in self.upload_records:
            if rec.done:
                continue
            key = recipient_group_key(rec.order, self.postal_db)
            address_groups.setdefault(key, []).append(rec)
        for records in address_groups.values():
            order_ids = {r.order_id() for r in records}
            trackings = {t for r in records for t in r.tracking_numbers if t}
            if len(order_ids) > 1 and trackings and len(trackings) < len(order_ids):
                gid = f"C{group_index}"
                group_index += 1
                adopted = sorted(trackings)[0]
                for rec in records:
                    if rec.process_type != "分割" and not rec.order.bundle_id:
                        rec.process_type = "同梱"
                        rec.group_id = gid
                        rec.adopted_tracking = adopted
        self.upload_group_counter = group_index

    def set_upload_process_type(self, process_type: str) -> None:
        records = [rec for rec in self.selected_upload_records() if not rec.done]
        if not records:
            messagebox.showwarning(APP_TITLE, "対象行を選択してください。")
            return
        gid = ""
        if process_type == "同梱":
            gid = f"C{self.upload_group_counter}"
            self.upload_group_counter += 1
            adopted = next((t for rec in records for t in rec.tracking_numbers if t), "")
        elif process_type == "分割":
            gid = f"S{self.upload_group_counter}"
            self.upload_group_counter += 1
            adopted = ""
        else:
            adopted = ""
        for rec in records:
            if process_type == "分割" and len(rec.tracking_numbers) < 2:
                existing = joined_tracking_numbers(rec.tracking_numbers)
                prompt = "追加する荷物番号を入力してください。"
                if existing:
                    prompt += f"\n現在の荷物番号: {existing}"
                value = simpledialog.askstring(APP_TITLE, prompt, parent=self.root)
                value = clean(value or "")
                if not value:
                    continue
                extra_numbers = [clean(part) for part in re.split(r"[\s,，/／]+", value) if clean(part)]
                for number in extra_numbers:
                    if number not in rec.tracking_numbers:
                        rec.tracking_numbers.append(number)
            if process_type == "通常" and len(rec.tracking_numbers) > 1:
                selected = self.choose_tracking_number(
                    "採用荷物番号",
                    f"{rec.order_id()} の通常発送で使う荷物番号を選択してください。",
                    rec.tracking_numbers,
                )
                if not selected:
                    continue
                rec.tracking_numbers = [selected]
                rec.adopted_tracking = selected
            rec.process_type = process_type
            rec.group_id = gid if process_type in {"同梱", "分割"} else ""
            if process_type == "同梱" and adopted:
                rec.adopted_tracking = adopted
            elif process_type == "分割":
                self.sync_upload_adopted_tracking(rec)
            elif process_type == "通常" and rec.tracking_numbers:
                rec.adopted_tracking = rec.tracking_numbers[0]
            rec.upload = True
        self.refresh_upload_tree()

    def exclude_upload_selected(self) -> None:
        records = [rec for rec in self.selected_upload_records() if not rec.done]
        for rec in records:
            rec.upload = False
            rec.process_type = "除外"
        self.refresh_upload_tree()

    def adopt_tracking_for_selected(self) -> None:
        records = [rec for rec in self.selected_upload_records() if not rec.done]
        if not records:
            return
        candidates = sorted({t for rec in records for t in rec.tracking_numbers if t})
        if not candidates:
            messagebox.showwarning(APP_TITLE, "選択行に荷物番号がありません。")
            return
        win = tk.Toplevel(self.root)
        win.title("採用荷物番号")
        win.geometry("360x160")
        var = tk.StringVar(value=candidates[0])
        ttk.Label(win, text="採用する荷物番号を選択してください。").pack(padx=10, pady=10)
        ttk.Combobox(win, textvariable=var, values=candidates, state="readonly", width=28).pack(padx=10, pady=5)
        def apply():
            gid = next((rec.group_id for rec in records if rec.process_type == "同梱" and rec.group_id), "")
            if not gid:
                gid = f"C{self.upload_group_counter}"
                self.upload_group_counter += 1
            for rec in records:
                rec.adopted_tracking = var.get()
                rec.process_type = "同梱"
                rec.group_id = gid
                rec.upload = True
            self.refresh_upload_tree()
            win.destroy()
        ttk.Button(win, text="適用", command=apply).pack(pady=10)

    def open_upload_message_settings(self) -> None:
        self.open_template_settings()

    def open_template_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("テンプレート設定")
        win.geometry("1080x680")
        win.transient(self.root)

        container = ttk.Frame(win, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(3, weight=1)

        method_rows = [dict(row) for row in self.message_templates]
        event_rows = [dict(row) for row in self.event_templates]

        method_header = ttk.Frame(container)
        method_header.grid(row=0, column=0, sticky="ew")
        method_header.columnconfigure(0, weight=1)
        ttk.Label(method_header, text=f"配送方法別テンプレート: {SHIPPING_MESSAGE_TEMPLATE_CSV}").grid(row=0, column=0, sticky="w")
        ttk.Button(method_header, text="配送方法を編集", command=lambda: edit_method()).grid(row=0, column=1, sticky="e")
        method_tree = ttk.Treeview(
            container,
            columns=("enabled", "invoice_code", "carrier", "method", "message1", "tracking_label", "message2"),
            show="headings",
            height=9,
            selectmode="browse",
        )
        for key, label, width in [
            ("enabled", "有効", 55), ("invoice_code", "コード", 70), ("carrier", "運送会社", 130),
            ("method", "発送方法", 150), ("message1", "メッセージ1", 220),
            ("tracking_label", "荷物番号行", 230), ("message2", "メッセージ2", 220),
        ]:
            method_tree.heading(key, text=label)
            method_tree.column(key, width=width, minwidth=min(width, 80), stretch=False)
        method_tree.grid(row=1, column=0, sticky="nsew", pady=(4, 10))

        event_header = ttk.Frame(container)
        event_header.grid(row=2, column=0, sticky="ew")
        event_header.columnconfigure(0, weight=1)
        ttk.Label(event_header, text=f"共通テンプレート: {SHIPPING_EVENT_TEMPLATE_CSV}").grid(row=0, column=0, sticky="w")
        ttk.Button(event_header, text="共通文を編集", command=lambda: edit_event()).grid(row=0, column=1, sticky="e")
        event_tree = ttk.Treeview(
            container,
            columns=("enabled", "event", "label", "message"),
            show="headings",
            height=6,
            selectmode="browse",
        )
        for key, label, width in [
            ("enabled", "有効", 55), ("event", "種類", 110), ("label", "表示名", 160), ("message", "文章", 650),
        ]:
            event_tree.heading(key, text=label)
            event_tree.column(key, width=width, minwidth=min(width, 80), stretch=False)
        event_tree.grid(row=3, column=0, sticky="nsew", pady=(4, 10))

        def preview(value: str, limit: int = 60) -> str:
            return gui_preview(str(value).replace("\n", " / "), limit)

        def refresh_method_tree():
            method_tree.delete(*method_tree.get_children())
            for idx, row in enumerate(method_rows):
                method_tree.insert("", tk.END, iid=str(idx), values=(
                    "✓" if template_enabled(row.get("enabled", "1")) else "",
                    row.get("invoice_code", ""),
                    row.get("carrier", ""),
                    row.get("method", ""),
                    preview(row.get("message1", "")),
                    preview(row.get("tracking_label", "")),
                    preview(row.get("message2", "")),
                ))

        def refresh_event_tree():
            event_tree.delete(*event_tree.get_children())
            for idx, row in enumerate(event_rows):
                event_tree.insert("", tk.END, iid=str(idx), values=(
                    "✓" if template_enabled(row.get("enabled", "1")) else "",
                    row.get("event", ""),
                    row.get("label", ""),
                    preview(row.get("message", ""), 90),
                ))

        def text_value(parent, initial: str, height: int = 4):
            widget = tk.Text(parent, height=height, wrap="word")
            widget.insert("1.0", initial or "")
            return widget

        def edit_method(_event=None):
            selection = method_tree.selection()
            if not selection:
                return
            idx = int(selection[0])
            row = method_rows[idx]
            edit_win = tk.Toplevel(win)
            edit_win.title("配送方法別テンプレート編集")
            edit_win.geometry("760x620")
            edit_win.transient(win)
            frame = ttk.Frame(edit_win, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            frame.columnconfigure(1, weight=1)

            enabled_var = tk.BooleanVar(value=template_enabled(row.get("enabled", "1")))
            code_var = tk.StringVar(value=row.get("invoice_code", ""))
            carrier_var = tk.StringVar(value=row.get("carrier", ""))
            method_var = tk.StringVar(value=row.get("method", ""))
            no_tracking_var = tk.StringVar(value=row.get("no_tracking_message", "未登録"))
            ttk.Checkbutton(frame, text="有効", variable=enabled_var).grid(row=0, column=0, sticky="w", pady=2)
            for r, (label, var, width) in enumerate([
                ("送り状コード", code_var, 12),
                ("運送会社名", carrier_var, 28),
                ("発送方法", method_var, 28),
                ("番号なし表示", no_tracking_var, 20),
            ], start=1):
                ttk.Label(frame, text=label).grid(row=r, column=0, sticky="e", padx=4, pady=3)
                ttk.Entry(frame, textvariable=var, width=width).grid(row=r, column=1, sticky="w", padx=4, pady=3)
            ttk.Label(frame, text="メッセージ1").grid(row=5, column=0, sticky="nw", padx=4, pady=3)
            message1 = text_value(frame, row.get("message1", ""), 5)
            message1.grid(row=5, column=1, sticky="ew", padx=4, pady=3)
            ttk.Label(frame, text="荷物番号行").grid(row=6, column=0, sticky="nw", padx=4, pady=3)
            tracking_label = text_value(frame, row.get("tracking_label", "{carrier} {method}：{tracking}"), 3)
            tracking_label.grid(row=6, column=1, sticky="ew", padx=4, pady=3)
            ttk.Label(frame, text="メッセージ2").grid(row=7, column=0, sticky="nw", padx=4, pady=3)
            message2 = text_value(frame, row.get("message2", ""), 5)
            message2.grid(row=7, column=1, sticky="ew", padx=4, pady=3)
            ttk.Label(frame, text="使用可能: {carrier} {method} {tracking}").grid(row=8, column=1, sticky="w", padx=4, pady=(2, 10))

            def apply_edit():
                row.update({
                    "invoice_code": clean(code_var.get()),
                    "carrier": clean(carrier_var.get()),
                    "method": clean(method_var.get()),
                    "message1": message1.get("1.0", "end-1c"),
                    "tracking_label": tracking_label.get("1.0", "end-1c"),
                    "message2": message2.get("1.0", "end-1c"),
                    "no_tracking_message": clean(no_tracking_var.get()) or "未登録",
                    "enabled": "1" if enabled_var.get() else "0",
                })
                refresh_method_tree()
                edit_win.destroy()

            ttk.Button(frame, text="保存", command=apply_edit).grid(row=9, column=1, sticky="e", pady=8)

        def edit_event(_event=None):
            selection = event_tree.selection()
            if not selection:
                return
            idx = int(selection[0])
            row = event_rows[idx]
            edit_win = tk.Toplevel(win)
            edit_win.title("共通テンプレート編集")
            edit_win.geometry("680x360")
            edit_win.transient(win)
            frame = ttk.Frame(edit_win, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            frame.columnconfigure(1, weight=1)
            enabled_var = tk.BooleanVar(value=template_enabled(row.get("enabled", "1")))
            label_var = tk.StringVar(value=row.get("label", ""))
            ttk.Checkbutton(frame, text="有効", variable=enabled_var).grid(row=0, column=0, sticky="w", pady=2)
            ttk.Label(frame, text="種類").grid(row=1, column=0, sticky="e", padx=4, pady=3)
            ttk.Label(frame, text=row.get("event", "")).grid(row=1, column=1, sticky="w", padx=4, pady=3)
            ttk.Label(frame, text="表示名").grid(row=2, column=0, sticky="e", padx=4, pady=3)
            ttk.Entry(frame, textvariable=label_var).grid(row=2, column=1, sticky="ew", padx=4, pady=3)
            ttk.Label(frame, text="文章").grid(row=3, column=0, sticky="nw", padx=4, pady=3)
            message = text_value(frame, row.get("message", ""), 7)
            message.grid(row=3, column=1, sticky="ew", padx=4, pady=3)

            def apply_edit():
                row.update({
                    "label": clean(label_var.get()),
                    "message": message.get("1.0", "end-1c"),
                    "enabled": "1" if enabled_var.get() else "0",
                })
                refresh_event_tree()
                edit_win.destroy()

            ttk.Button(frame, text="保存", command=apply_edit).grid(row=4, column=1, sticky="e", pady=8)

        def save():
            self.message_templates = method_rows
            self.event_templates = event_rows
            save_message_templates(Path(__file__).resolve().parent, self.message_templates, self.event_templates)
            win.destroy()
            messagebox.showinfo(APP_TITLE, "テンプレート設定を保存しました。")

        def show_csv_help():
            help_win = tk.Toplevel(win)
            help_win.title("テンプレートCSV仕様")
            help_win.geometry("860x620")
            help_win.transient(win)
            frame = ttk.Frame(help_win, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            text = tk.Text(frame, wrap="word")
            text.grid(row=0, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
            scroll.grid(row=0, column=1, sticky="ns")
            text.configure(yscrollcommand=scroll.set)
            text.insert("1.0", f"""テンプレートCSV仕様

CSVはこのスクリプトと同じフォルダに保存されます。
Excelで直接編集できます。文字コードは UTF-8 BOM です。

1. 配送方法別テンプレート
ファイル名:
{SHIPPING_MESSAGE_TEMPLATE_CSV}

列:
invoice_code
  送り状種類コードです。例: A, 0, 8

carrier
  運送会社名です。例: ヤマト運輸

method
  発送方法名です。例: ネコポス, 宅急便

message1
  荷物番号行の前に入る文章です。

tracking_label
  荷物番号を入れる行の書式です。
  使用可能な置換文字:
    {{carrier}}  運送会社名
    {{method}}   発送方法名
    {{tracking}} 荷物番号

  例:
    {{carrier}} {{method}}：{{tracking}}

message2
  荷物番号行の後に入る文章です。

no_tracking_message
  荷物番号が空欄の場合に {{tracking}} の代わりに入る文字です。
  例: 未登録, 追跡番号なし

enabled
  1 で有効、0 で無効です。


2. 共通テンプレート
ファイル名:
{SHIPPING_EVENT_TEMPLATE_CSV}

列:
event
  before    冒頭文
  combined  同梱発送時の文章
  multiple  分割発送時の文章
  after     末尾文

label
  GUI上の表示名です。

message
  文章です。

enabled
  1 で有効、0 で無効です。


改行について:
GUIでは普通にEnterで改行できます。
CSVを直接編集する場合は、文章中の改行を \\n と書いてください。

例:
ポスト投函でのお届けです。\\n郵便受けをご確認ください。

GUIで読み込むと下記のように表示されます。
ポスト投函でのお届けです。
郵便受けをご確認ください。


注意:
列名は変更しないでください。
CSVを直接編集した場合は、次回起動時またはテンプレート設定画面を開き直した時に反映されます。
""")
            text.configure(state="disabled")
            ttk.Button(frame, text="閉じる", command=help_win.destroy).grid(row=1, column=0, columnspan=2, sticky="e", pady=(8, 0))

        method_tree.bind("<Double-1>", edit_method)
        event_tree.bind("<Double-1>", edit_event)
        refresh_method_tree()
        refresh_event_tree()

        bottom = ttk.Frame(container)
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Button(bottom, text="CSV仕様", command=show_csv_help).grid(row=0, column=0, sticky="w")
        action_buttons = ttk.Frame(bottom)
        action_buttons.grid(row=0, column=1, sticky="e")
        ttk.Button(action_buttons, text="保存", command=save).pack(side=tk.LEFT, padx=4)
        ttk.Button(action_buttons, text="閉じる", command=win.destroy).pack(side=tk.LEFT, padx=4)

    def upload_shipping_method_name(self, code: str) -> str:
        return SHIPPING_METHOD_NAMES.get(code, f"ヤマト運輸({code})")

    def upload_method_message(self, code: str) -> str:
        return str(self.upload_messages.get("method_messages", {}).get(code, "")).strip()

    def method_template(self, code: str) -> Dict[str, str]:
        code = invoice_code(code)
        for row in self.message_templates:
            if clean(row.get("invoice_code", "")) == code and template_enabled(row.get("enabled", "1")):
                return row
        fallback = default_method_template_rows(self.upload_messages)
        return next((row for row in fallback if row.get("invoice_code") == code), {
            "invoice_code": code,
            "carrier": "ヤマト運輸",
            "method": INVOICE_TYPE_NAMES.get(code, code),
            "message1": "",
            "tracking_label": "{carrier} {method}：{tracking}",
            "message2": "",
            "no_tracking_message": "未登録",
            "enabled": "1",
        })

    def event_template_message(self, event: str) -> str:
        for row in self.event_templates:
            if clean(row.get("event", "")) == event and template_enabled(row.get("enabled", "1")):
                return str(row.get("message", "")).strip()
        return str(self.upload_messages.get(event, "")).strip()

    def format_tracking_line(self, template: Dict[str, str], tracking: str) -> str:
        tracking_text = clean(tracking) or clean(template.get("no_tracking_message", "")) or "未登録"
        label = template.get("tracking_label", "") or "{carrier} {method}：{tracking}"
        values = {
            "carrier": template.get("carrier", ""),
            "method": template.get("method", ""),
            "tracking": tracking_text,
        }
        try:
            return label.format(**values).strip()
        except Exception:
            return f"{values['carrier']} {values['method']}：{tracking_text}".strip()

    def append_template_tracking_block(self, lines: List[str], code: str, trackings: List[str]) -> None:
        template = self.method_template(code)
        message1 = str(template.get("message1", "")).strip()
        message2 = str(template.get("message2", "")).strip()
        if message1:
            lines.append(message1)
        for tracking in trackings or [""]:
            lines.append(self.format_tracking_line(template, tracking))
        if message2:
            lines.append(message2)

    def build_tracking_info(self, rec: UploadRecord, group_records: List[UploadRecord]) -> str:
        lines = [self.event_template_message("before")]
        process_type = rec.process_type
        if process_type == "同梱":
            lines.append(self.event_template_message("combined"))
            lines.extend([f"注文ID: {r.order_id()}" for r in group_records])
            tracking = rec.adopted_tracking or next((r.adopted_tracking for r in group_records if r.adopted_tracking), "")
            self.append_template_tracking_block(lines, rec.order.invoice_type, [tracking])
        elif process_type == "分割":
            lines.append(self.event_template_message("multiple"))
            trackings = rec.tracking_numbers or [rec.adopted_tracking]
            self.append_template_tracking_block(lines, rec.order.invoice_type, [tracking for tracking in trackings if tracking] or [""])
        else:
            tracking = rec.adopted_tracking or (rec.tracking_numbers[0] if rec.tracking_numbers else "")
            self.append_template_tracking_block(lines, rec.order.invoice_type, [tracking])
        lines.append(self.event_template_message("after"))
        return "\n".join([line for line in lines if line])

    def upload_shipping_date(self, rec: UploadRecord, group_records: List[UploadRecord]) -> str:
        if rec.process_type != "同梱":
            return rec.order.delivery_date

        adopted_tracking = rec.adopted_tracking or next(
            (group_rec.adopted_tracking for group_rec in group_records if group_rec.adopted_tracking),
            ""
        )
        if adopted_tracking:
            for group_rec in group_records:
                if (
                    group_rec.adopted_tracking == adopted_tracking
                    or adopted_tracking in group_rec.tracking_numbers
                ):
                    if group_rec.order.delivery_date:
                        return group_rec.order.delivery_date

        return rec.order.delivery_date or next(
            (group_rec.order.delivery_date for group_rec in group_records if group_rec.order.delivery_date),
            ""
        )

    def export_mercari_upload_csv(self) -> None:
        if not self.upload_records:
            messagebox.showwarning(APP_TITLE, "受注CSVとB2出荷データを読み込んでください。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"メルカリショップスアップロードデータ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        group_map: Dict[str, List[UploadRecord]] = {}
        for rec in self.upload_records:
            if rec.group_id:
                group_map.setdefault(rec.group_id, []).append(rec)
        output_records: List[UploadRecord] = []
        try:
            skipped_no_tracking = 0
            with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(["order_id", "shipping_method", "shipping_tracking_info", "shipping_date"])
                for rec in self.upload_records:
                    if rec.done or not rec.upload:
                        continue
                    group_records = group_map.get(rec.group_id, [rec])
                    if not self.upload_record_has_tracking(rec, group_records):
                        skipped_no_tracking += 1
                        continue
                    tracking_info = self.build_tracking_info(rec, group_records)
                    shipping_method = self.upload_shipping_method_name(rec.order.invoice_type)
                    shipping_date = self.upload_shipping_date(rec, group_records)
                    writer.writerow([rec.order_id(), shipping_method, tracking_info, shipping_date])
                    output_records.append(rec)
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        for rec in output_records:
            rec.done = True
        self.refresh_upload_tree()
        suffix = f"\n荷物番号なしのため未出力: {skipped_no_tracking}件" if skipped_no_tracking else ""
        done_suffix = f"\n済に移行: {len(output_records)}件"
        self.upload_status.set(f"メルカリアップロードCSVを出力しました: {path}{suffix}{done_suffix}")
        messagebox.showinfo(APP_TITLE, f"出力しました。\n{path}{suffix}{done_suffix}")

    def update_unpaid_order_from_loaded(self, existing: OrderRecord, loaded: OrderRecord) -> bool:
        was_unpaid = not clean(existing.source.get("shipping_name", ""))
        now_shippable = bool(clean(loaded.source.get("shipping_name", "")))
        if not was_unpaid or not now_shippable:
            return False
        existing.source.update(loaded.source)
        existing.selected = True
        return True

    def load_csv(self) -> None:
        if not self.csv_path.get():
            messagebox.showwarning(APP_TITLE, "受注CSVを選択してください。")
            return
        try:
            loaded_records = read_orders(Path(self.csv_path.get()))
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.reset_ship_date_to_today()
        skipped_existing = 0
        updated_unpaid = 0
        added_count = len(loaded_records)
        append_mode = bool(self.records)
        if append_mode:
            existing_by_order_id = {
                record.value("order_id"): record
                for record in self.records
                if record.value("order_id")
            }
            existing_order_ids = set(existing_by_order_id.keys())
            numeric_row_ids = [int(record.row_id) for record in self.records if str(record.row_id).isdigit()]
            next_row_id = max(numeric_row_ids, default=0) + 1
            added_records = []
            for record in loaded_records:
                order_id = record.value("order_id")
                if order_id and order_id in existing_order_ids:
                    if self.update_unpaid_order_from_loaded(existing_by_order_id[order_id], record):
                        updated_unpaid += 1
                    skipped_existing += 1
                    continue
                record.row_id = str(next_row_id)
                next_row_id += 1
                added_records.append(record)
                if order_id:
                    existing_order_ids.add(order_id)
            self.records.extend(added_records)
            added_count = len(added_records)
        else:
            self.records = loaded_records
            self.bundle_counter = 1
        self.group_candidates.set(False)
        self.update_group_candidates_button()
        self.refresh_tree()
        self.sync_upload_records_with_orders()
        if not append_mode:
            self.auto_classify_upload_records()
        self.refresh_upload_tree()
        db_status = self.postal_db.summary() if self.postal_db else "郵便番号DBなし"
        if skipped_existing:
            self.status.set(
                f"受注CSVを追加読込しました。新規: {added_count}件 / 既存: {skipped_existing}件 / "
                f"未入金更新: {updated_unpaid}件 / "
                f"合計: {len(self.records)}件。確認あり: {self.last_warning_count}件。{db_status}"
            )
        else:
            self.status.set(f"{len(self.records)}件を読み込みました。確認あり: {self.last_warning_count}件。{db_status}")

    def searchable_texts(self, record: OrderRecord, address: tuple[str, str, str, str]) -> Dict[str, str]:
        state, city, address1, address2 = address
        values = {
            "注文ID": record.value("order_id"),
            "送付先": recipient_name(record),
            "注文者": record.value("buyer_name"),
            "商品名": record.value("product_name"),
            "住所": " ".join([state, city, address1, address2]),
            "郵便番号": record.value("shipping_postal_code"),
            "送り状種類": invoice_label(record.invoice_type),
            "同梱番号": record.bundle_id,
        }
        values["すべて"] = " ".join(values.values())
        return values

    def matches_search(self, record: OrderRecord, address: tuple[str, str, str, str]) -> bool:
        text = self.search_text.get().strip().lower()
        if not text:
            return True
        target = self.search_target.get()
        values = self.searchable_texts(record, address)
        haystack = values.get(target, values["すべて"]).lower()
        return all(word in haystack for word in text.split())

    def apply_search_filter(self, _event=None) -> None:
        self.search_current_pos = -1
        self.refresh_tree(save_session=False)

    def clear_search_filter(self) -> None:
        self.search_text.set("")
        self.search_only.set(True)
        self.output_filter_mode.set("全表示")
        self.update_output_filter_button()
        self.search_current_pos = -1
        self.refresh_tree(save_session=False)

    def update_search_result_text(self, total_rows: Optional[int] = None) -> None:
        if self.search_text.get().strip():
            total = len(self.search_match_indices)
            if total and self.search_current_pos >= 0:
                self.search_result_text.set(f"検索: {self.search_current_pos + 1}/{total}件")
            else:
                self.search_result_text.set(f"検索: {total}件")
        else:
            self.search_result_text.set(f"表示: {len(self.records) if total_rows is None else total_rows}件")

    def select_next_search_match(self) -> None:
        if not self.search_text.get().strip():
            return
        if not self.search_match_indices:
            self.refresh_tree(save_session=False)
        visible_matches = [idx for idx in self.search_match_indices if str(idx) in self.tree.get_children("")]
        if not visible_matches:
            return
        if self.search_current_pos < 0:
            self.search_current_pos = self.search_match_indices.index(visible_matches[0])
        else:
            current_idx = self.search_match_indices[self.search_current_pos] if self.search_current_pos < len(self.search_match_indices) else None
            try:
                visible_pos = visible_matches.index(current_idx)
                self.search_current_pos = self.search_match_indices.index(visible_matches[(visible_pos + 1) % len(visible_matches)])
            except ValueError:
                self.search_current_pos = self.search_match_indices.index(visible_matches[0])
        idx = self.search_match_indices[self.search_current_pos]
        iid = str(idx)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self.on_select()
        self.update_search_result_text()

    def select_visible_rows(self) -> None:
        visible = [str(idx) for idx in self.visible_record_indices]
        self.tree.selection_set(visible)
        self.selected_count.set(f"{len(visible)}件選択")

    def clear_visible_selection(self) -> None:
        visible = [str(idx) for idx in self.visible_record_indices]
        self.tree.selection_remove(visible)
        self.selected_count.set(f"{len(self.tree.selection())}件選択")

    def mark_selected_done(self) -> None:
        records = self.selected_records()
        if not records:
            messagebox.showwarning(APP_TITLE, "済にする行を選択してください。")
            return
        for record in records:
            record.done = True
        self.refresh_tree()
        self.status.set(f"{len(records)}件を済にしました。済の行は選択されていても出力されません。")

    def clear_selected_done(self) -> None:
        records = self.selected_records()
        if not records:
            messagebox.showwarning(APP_TITLE, "済解除する行を選択してください。")
            return
        for record in records:
            record.done = False
        self.refresh_tree()
        self.status.set(f"{len(records)}件の済を解除しました。")

    def delete_selected_orders(self) -> None:
        records = self.selected_records()
        if not records:
            messagebox.showwarning(APP_TITLE, "削除する行を選択してください。")
            return
        done_count = sum(1 for record in records if record.done)
        message = f"選択した{len(records)}件の注文を一覧から削除しますか？\n出荷後アップロード側の同じ注文も削除されます。"
        if done_count:
            message += f"\n\n済の注文が{done_count}件含まれています。"
        if not messagebox.askyesno(APP_TITLE, message):
            return
        delete_ids = {id(record) for record in records}
        self.records = [record for record in self.records if id(record) not in delete_ids]
        self.upload_records = [rec for rec in self.upload_records if id(rec.order) not in delete_ids]
        self.tree.selection_remove(self.tree.selection())
        if hasattr(self, "upload_tree"):
            self.upload_tree.selection_remove(self.upload_tree.selection())
        self.refresh_tree()
        self.refresh_upload_tree()
        self.selected_count.set("0件選択")
        self.status.set(f"{len(records)}件を削除しました。")

    def select_output_visible_only(self) -> None:
        if not self.records:
            return
        visible = set(self.visible_record_indices)
        checked_count = 0
        unchecked_count = 0
        for idx, record in enumerate(self.records):
            if record.done:
                continue
            if idx in visible:
                if not record.selected:
                    record.selected = True
                checked_count += 1
            elif record.selected:
                record.selected = False
                unchecked_count += 1
        self.refresh_tree()
        self.status.set(f"表示行のみ出力対象にしました。✓: {checked_count}件 / 解除: {unchecked_count}件（済は変更なし）")

    def refresh_tree(self, save_session: bool = True) -> None:
        self.tree.delete(*self.tree.get_children())
        group_counts: Dict[tuple, int] = {}
        view_infos = []
        self.record_warnings_by_id = {}
        for record in self.records:
            key = recipient_group_key(record, self.postal_db)
            warnings = validate_record(record, self.postal_db)
            address = normalized_address_fields(record, self.postal_db)
            group_counts[key] = group_counts.get(key, 0) + 1
            self.record_warnings_by_id[id(record)] = warnings
            view_infos.append({
                "record": record,
                "group_key": key,
                "warnings": warnings,
                "address": address,
                "search_match": self.matches_search(record, address),
            })
        self.last_warning_count = sum(1 for info in view_infos if info["warnings"])
        has_search = bool(self.search_text.get().strip())
        self.search_match_indices = [idx for idx, info in enumerate(view_infos) if has_search and info["search_match"]]
        if self.search_current_pos >= len(self.search_match_indices):
            self.search_current_pos = -1
        self.update_search_result_text(total_rows=len(view_infos))
        self.visible_record_indices = []
        output_filter = self.output_filter_mode.get()
        for idx, info in enumerate(view_infos):
            record = info["record"]
            if self.search_only.get() and not info["search_match"]:
                continue
            if output_filter == "✓表示" and (not record.selected or record.done):
                continue
            if output_filter == "済表示" and not record.done:
                continue
            self.visible_record_indices.append(idx)
            iid = str(idx)
            warnings = info["warnings"]
            bundled = group_counts.get(info["group_key"], 0) > 1
            if warnings and record.bundle_id:
                tags = ("manual_bundle_warning",)
            elif record.bundle_id:
                tags = ("manual_bundle",)
            elif warnings and bundled:
                tags = ("bundle_warning",)
            elif warnings:
                tags = ("warning",)
            elif bundled:
                tags = ("bundle",)
            else:
                tags = ()
            state, city, address1, address2 = info["address"]
            if "未入金のため出荷不可" in warnings:
                warning_mark = "未入金注" if record.note.strip() else "未入金"
            elif warnings and record.note.strip():
                warning_mark = "!注"
            elif warnings:
                warning_mark = "!"
            elif record.note.strip():
                warning_mark = "注"
            else:
                warning_mark = ""
            self.tree.insert("", tk.END, iid=iid, values=(
                warning_mark,
                "済" if record.done else ("✓" if record.selected else ""),
                record.value("order_id"),
                record.value("purchase_date"),
                f"【同梱{record.bundle_id}】{record.value('shipping_name')}" if record.bundle_id else record.value("shipping_name"),
                state,
                city,
                record.value("shipping_postal_code"),
                gui_preview(address1, 48),
                gui_preview(address2, 48),
                invoice_label(record.invoice_type),
                record.copies,
                gui_preview(record.value("product_name"), 120),
                record.value("quantity"),
                record.delivery_date,
                delivery_time_label(record.delivery_time),
            ), tags=tags)
        if save_session:
            self.schedule_current_session_save()

    def selected_records(self) -> List[OrderRecord]:
        return [self.records[int(iid)] for iid in self.tree.selection()]

    def on_select(self, _event=None) -> None:
        records = self.selected_records()
        self.selected_count.set(f"{len(records)}件選択")
        if records:
            self.invoice_type_var.set(invoice_label(records[0].invoice_type))
            self.delivery_date_var.set(records[0].delivery_date)
            self.delivery_time_var.set(delivery_time_label(records[0].delivery_time))
            self.copies_var.set(records[0].copies)
            warning_lines = []
            for record in records[:3]:
                warnings = self.record_warnings_by_id.get(id(record))
                if warnings is None:
                    warnings = validate_record(record, self.postal_db)
                if warnings:
                    warning_lines.append(f"{record.value('order_id')}: " + "、".join(warnings))
            if warning_lines:
                suffix = " ほか" if len(records) > 3 else ""
                self.status.set("住所確認: " + " / ".join(warning_lines) + suffix)

    def toggle_selected(self, _event=None) -> None:
        records = self.selected_records()
        if not records:
            return
        new_state = not all(r.selected for r in records)
        for record in records:
            record.selected = new_state
        self.refresh_tree()

    def toggle_bundle_selected(self) -> None:
        records = self.selected_records()
        if not records:
            messagebox.showwarning(APP_TITLE, "同梱にする行を選択してください。")
            return
        bundle_ids = {record.bundle_id for record in records if record.bundle_id}
        if len(bundle_ids) == 1 and all(record.bundle_id in bundle_ids for record in records):
            bundle_id = next(iter(bundle_ids))
            for record in self.records:
                if record.bundle_id == bundle_id:
                    record.bundle_id = ""
            self.status.set(f"同梱{bundle_id}を解除しました。")
        else:
            if len(records) < 2:
                messagebox.showwarning(APP_TITLE, "同梱は2行以上を選択してください。")
                return
            bundle_id = f"B{self.bundle_counter}"
            self.bundle_counter += 1
            for record in records:
                record.bundle_id = bundle_id
                record.selected = True
            self.status.set(f"{len(records)}件を同梱{bundle_id}にしました。送り状は1枚だけ出力されます。")
        self.refresh_tree()
        self.initialize_upload_records()
        self.refresh_upload_tree()

    def begin_cell_edit(self, event) -> None:
        if self.edit_widget is not None:
            self.edit_widget.destroy()
            self.edit_widget = None
            self.edit_context = None

        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        column_index = int(column_id.replace("#", "")) - 1
        columns = list(self.tree["columns"])
        if column_index < 0 or column_index >= len(columns):
            return
        key = columns[column_index]
        record = self.records[int(row_id)]

        if key == "selected":
            self.tree.selection_set(row_id)
            self.toggle_selected()
            return
        if key == "warning":
            self.show_warning_window(record)
            return

        editable_source_keys = {
            "purchase_date", "shipping_name", "shipping_state", "shipping_city",
            "shipping_postal_code", "shipping_address_1", "shipping_address_2",
            "product_name", "quantity",
        }
        editable_special_keys = {"delivery_date", "delivery_time", "invoice_type", "copies"}
        if key not in editable_source_keys and key not in editable_special_keys:
            return

        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, width, height = bbox
        if key in {"shipping_state", "shipping_city", "shipping_address_1", "shipping_address_2"}:
            state, city, address1, address2 = normalized_address_fields(record, self.postal_db)
            current = {
                "shipping_state": state,
                "shipping_city": city,
                "shipping_address_1": address1,
                "shipping_address_2": address2,
            }[key]
        elif key in editable_source_keys:
            current = record.value(key)
        elif key == "delivery_date":
            current = record.delivery_date
        elif key == "delivery_time":
            current = delivery_time_label(record.delivery_time)
        elif key == "invoice_type":
            current = invoice_label(record.invoice_type)
        elif key == "copies":
            current = str(record.copies)
        else:
            current = self.tree.set(row_id, key)

        if key == "invoice_type":
            widget = ttk.Combobox(self.tree, values=INVOICE_TYPE_LABELS, state="readonly")
            widget.set(invoice_label(record.invoice_type))
        elif key == "delivery_time":
            widget = ttk.Combobox(self.tree, values=DELIVERY_TIME_LABELS, state="readonly")
            widget.set(delivery_time_label(record.delivery_time))
        else:
            widget = ttk.Entry(self.tree)
            widget.insert(0, str(current))

        widget.place(x=x, y=y, width=width, height=height)
        widget.focus_set()
        self.edit_widget = widget
        self.edit_context = {"record": record, "key": key, "widget": widget, "cursor": len(str(current))}
        self.last_edit_context = {"record": record, "key": key, "cursor": len(str(current)), "text": str(current)}

        def remember_cursor(_event=None):
            try:
                self.edit_context["cursor"] = widget.index(tk.INSERT)
                self.last_edit_context = {
                    "record": record,
                    "key": key,
                    "cursor": self.edit_context["cursor"],
                    "text": widget.get(),
                }
            except Exception:
                pass

        def commit(_event=None):
            value = widget.get()
            try:
                cursor = widget.index(tk.INSERT)
            except Exception:
                cursor = self.edit_context.get("cursor", len(value)) if self.edit_context else len(value)
            self.last_edit_context = {"record": record, "key": key, "cursor": cursor, "text": value}
            if key in editable_source_keys:
                if key in {"shipping_state", "shipping_city", "shipping_address_1", "shipping_address_2"}:
                    self.apply_normalized_address_edit(record, key, value)
                else:
                    record.source[key] = value
            elif key == "delivery_date":
                record.delivery_date = value.strip()
            elif key == "delivery_time":
                record.delivery_time = delivery_time_code(value)
            elif key == "invoice_type":
                record.invoice_type = invoice_code(value)
            elif key == "copies":
                try:
                    record.copies = max(1, int(value))
                except Exception:
                    record.copies = 1
            widget.destroy()
            self.edit_widget = None
            self.edit_context = None
            self.refresh_tree()

        def cancel(_event=None):
            widget.destroy()
            self.edit_widget = None
            self.edit_context = None

        def delayed_focus_commit(_event=None):
            def run():
                if self.edit_widget is not widget:
                    return
                try:
                    focus = self.root.focus_get()
                except KeyError:
                    focus = None
                if focus == self.text_adjust_button:
                    return
                commit()
            self.root.after(80, run)

        widget.bind("<Return>", commit)
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", commit)
        else:
            widget.bind("<FocusOut>", delayed_focus_commit)
        widget.bind("<Escape>", cancel)
        widget.bind("<KeyRelease>", remember_cursor)
        widget.bind("<ButtonRelease-1>", remember_cursor)

    def apply_normalized_address_edit(self, record: OrderRecord, key: str, value: str) -> None:
        state, city, address1, address2 = normalized_address_fields(record, self.postal_db)
        if key == "shipping_state":
            state = value
        elif key == "shipping_city":
            city = value
        elif key == "shipping_address_1":
            address1 = value
        elif key == "shipping_address_2":
            address2 = value
        record.source["shipping_state"] = state
        record.source["shipping_city"] = city
        record.source["shipping_address_1"] = address1
        record.source["shipping_address_2"] = address2

    def move_text_after_cursor(self, _event=None):
        context = self.edit_context or self.last_edit_context
        if not context:
            messagebox.showinfo(APP_TITLE, "先に住所欄をダブルクリックして編集状態にしてください。")
            return "break"

        key = context.get("key")
        next_key_map = {
            "shipping_city": "shipping_address_1",
            "shipping_address_1": "shipping_address_2",
        }
        next_key = next_key_map.get(key)
        if not next_key:
            messagebox.showinfo(APP_TITLE, "文字数調整は「市区町村」「町・番地」の編集中に使用できます。")
            return "break"

        widget = context.get("widget") if self.edit_context else None
        record = context["record"]
        if widget is not None:
            try:
                cursor = widget.index(tk.INSERT)
            except Exception:
                cursor = context.get("cursor", 0)
            text = widget.get()
        else:
            cursor = context.get("cursor", 0)
            text = context.get("text", "")
        if cursor >= len(text):
            messagebox.showinfo(APP_TITLE, "カーソル以降に移動する文字がありません。")
            return "break"

        keep = text[:cursor]
        moving = text[cursor:]
        state, city, address1, address2 = normalized_address_fields(record, self.postal_db)

        if key == "shipping_city":
            city = keep
            address1 = moving + address1
        elif key == "shipping_address_1":
            address1 = keep
            address2 = moving + address2

        record.source["shipping_state"] = state
        record.source["shipping_city"] = city
        record.source["shipping_address_1"] = address1
        record.source["shipping_address_2"] = address2

        if widget is not None:
            widget.delete(0, tk.END)
            widget.insert(0, keep)
            widget.destroy()
        self.edit_widget = None
        self.edit_context = None
        self.last_edit_context = {"record": record, "key": next_key, "cursor": 0, "text": moving}
        self.refresh_tree()
        self.status.set(f"文字数調整: 「{moving}」を右隣の列へ移動しました。")
        return "break"

    def show_warning_window(self, record: OrderRecord) -> None:
        warnings = validate_record(record, self.postal_db)
        win = tk.Toplevel(self.root)
        win.title("住所確認")
        win.geometry("720x560")
        win.transient(self.root)
        win.grab_set()

        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        raw_text = (
            f"注文ID: {record.value('order_id')}\n"
            f"郵便番号: {record.value('shipping_postal_code')}\n"
            f"現在: {record.value('shipping_state')} {record.value('shipping_city')} "
            f"{record.value('shipping_address_1')} {record.value('shipping_address_2')}\n"
        )
        state, city, rest = normalized_address_parts(record, self.postal_db)
        normalized_text = f"正規化後: {state} {city} {rest}"
        ttk.Label(main, text=raw_text + normalized_text, justify=tk.LEFT).grid(row=0, column=0, sticky="w")

        message = "\n".join(warnings) if warnings else "現在、確認が必要な項目はありません。"
        ttk.Label(main, text=message, foreground="red" if warnings else "black", justify=tk.LEFT).grid(row=1, column=0, sticky="w", pady=(8, 8))

        button_frame = ttk.Frame(main)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        def apply_db_address():
            if not self.postal_db or not self.postal_db.loaded:
                return
            candidates = self.postal_db.lookup(record.value("shipping_postal_code"))
            if not candidates:
                return
            candidate = candidates[0]
            old_state = record.value("shipping_state")
            old_city = record.value("shipping_city")
            old_address = record.value("shipping_address_1") + record.value("shipping_address_2")
            extra = ""
            if old_state == candidate["state"] and old_city.startswith(candidate["city"]):
                extra = old_city[len(candidate["city"]):]
            if candidate["town"] and not (extra + old_address).startswith(candidate["town"]):
                extra = candidate["town"] + extra
            record.source["shipping_state"] = candidate["state"]
            record.source["shipping_city"] = candidate["city"]
            record.source["shipping_address_1"] = extra + old_address
            record.source["shipping_address_2"] = ""
            record.note = memo_text.get("1.0", "end-1c").strip()
            self.refresh_tree()
            win.destroy()

        ttk.Button(button_frame, text="郵便番号DBの住所を反映", command=apply_db_address).pack(side=tk.LEFT)

        ttk.Label(main, text="入力住所から郵便番号候補").grid(row=3, column=0, sticky="w")
        list_frame = ttk.Frame(main)
        list_frame.grid(row=4, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        candidate_tree = ttk.Treeview(list_frame, columns=("zipcode", "state", "city", "town"), show="headings", height=8)
        for key, label, width in [
            ("zipcode", "郵便番号", 90),
            ("state", "都道府県", 90),
            ("city", "市区町村", 160),
            ("town", "町域", 260),
        ]:
            candidate_tree.heading(key, text=label)
            candidate_tree.column(key, width=width)
        candidate_tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=candidate_tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        candidate_tree.configure(yscrollcommand=scroll.set)

        candidates = []
        if self.postal_db and self.postal_db.loaded:
            current_state, current_city, current_rest = normalized_address_parts(record, self.postal_db)
            candidates = self.postal_db.find_by_address(current_state, current_city, current_rest)
            if not candidates:
                candidates = self.postal_db.find_by_address(record.value("shipping_state"), record.value("shipping_city"), record.value("shipping_address_1"))
        for idx, item in enumerate(candidates):
            candidate_tree.insert("", tk.END, iid=str(idx), values=(
                f"{item['zipcode'][:3]}-{item['zipcode'][3:]}",
                item["state"],
                item["city"],
                item["town"],
            ))

        bottom = ttk.Frame(main)
        bottom.grid(row=5, column=0, sticky="e", pady=(10, 0))

        memo_frame = ttk.LabelFrame(main, text="確認メモ")
        memo_frame.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        memo_frame.columnconfigure(0, weight=1)
        memo_text = tk.Text(memo_frame, height=4, wrap="word")
        memo_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        memo_text.insert("1.0", record.note)

        def save_note():
            record.note = memo_text.get("1.0", "end-1c").strip()
            self.refresh_tree()
            self.status.set("確認メモを保存しました。")
            win.destroy()

        ttk.Button(memo_frame, text="保存", command=save_note).grid(row=0, column=1, padx=(0, 6), pady=6, sticky="ns")

        def apply_selected_zip():
            selection = candidate_tree.selection()
            if not selection:
                messagebox.showwarning(APP_TITLE, "候補を選択してください。", parent=win)
                return
            item = candidates[int(selection[0])]
            record.source["shipping_postal_code"] = f"{item['zipcode'][:3]}-{item['zipcode'][3:]}"
            record.source["shipping_state"] = item["state"]
            record.source["shipping_city"] = item["city"]
            old_rest = record.value("shipping_address_1") + record.value("shipping_address_2")
            if item["town"] and not old_rest.startswith(item["town"]):
                old_rest = item["town"] + old_rest
            record.source["shipping_address_1"] = old_rest
            record.source["shipping_address_2"] = ""
            record.note = memo_text.get("1.0", "end-1c").strip()
            self.refresh_tree()
            win.destroy()

        def close_window():
            record.note = memo_text.get("1.0", "end-1c").strip()
            self.refresh_tree()
            win.destroy()

        ttk.Button(bottom, text="選択した郵便番号を適用", command=apply_selected_zip).pack(side=tk.LEFT, padx=4)
        ttk.Button(bottom, text="閉じる", command=close_window).pack(side=tk.LEFT, padx=4)

    def apply_invoice_type(self) -> None:
        for record in self.selected_records():
            record.invoice_type = invoice_code(self.invoice_type_var.get())
        self.refresh_tree()

    def apply_delivery_date(self) -> None:
        for record in self.selected_records():
            record.delivery_date = self.delivery_date_var.get().strip()
        self.refresh_tree()

    def apply_delivery_time(self) -> None:
        for record in self.selected_records():
            record.delivery_time = delivery_time_code(self.delivery_time_var.get())
        self.refresh_tree()

    def apply_copies(self) -> None:
        try:
            copies = max(1, int(self.copies_var.get()))
        except Exception:
            copies = 1
        for record in self.selected_records():
            record.copies = copies
        self.refresh_tree()

    def apply_selected_changes(self) -> None:
        records = self.selected_records()
        if not records:
            messagebox.showwarning(APP_TITLE, "変更する行を選択してください。")
            return
        try:
            copies = max(1, int(self.copies_var.get()))
        except Exception:
            copies = 1
        for record in records:
            record.invoice_type = invoice_code(self.invoice_type_var.get())
            record.delivery_date = self.delivery_date_var.get().strip()
            record.delivery_time = delivery_time_code(self.delivery_time_var.get())
            record.copies = copies
        self.refresh_tree()
        self.status.set(f"{len(records)}件に送り状種類・お届け日・時間帯・枚数を適用しました。")

    def sort_by(self, key: str) -> None:
        if self.sort_column == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = key
            self.sort_reverse = False
        self.apply_current_sort()

    def apply_current_sort(self) -> None:
        key = self.sort_column or "purchase_date"
        address_cache: Dict[int, tuple[str, str, str]] = {}
        group_cache: Dict[int, tuple] = {}
        warning_cache: Dict[int, str] = {}

        def cached_address_parts(record: OrderRecord) -> tuple[str, str, str]:
            cache_key = id(record)
            if cache_key not in address_cache:
                address_cache[cache_key] = normalized_address_parts(record, self.postal_db)
            return address_cache[cache_key]

        def cached_group_key(record: OrderRecord) -> tuple:
            cache_key = id(record)
            if cache_key not in group_cache:
                group_cache[cache_key] = recipient_group_key(record, self.postal_db)
            return group_cache[cache_key]

        def cached_warnings(record: OrderRecord) -> str:
            cache_key = id(record)
            if cache_key not in warning_cache:
                warning_cache[cache_key] = " / ".join(validate_record(record, self.postal_db))
            return warning_cache[cache_key]

        def sort_key(record: OrderRecord):
            if key == "selected":
                base = (record.done, record.selected)
            elif key == "invoice_type":
                base = record.invoice_type
            elif key == "delivery_date":
                base = record.delivery_date
            elif key == "delivery_time":
                base = record.delivery_time
            elif key == "copies":
                base = record.copies
            elif key == "shipping_state":
                base = cached_address_parts(record)[0]
            elif key == "shipping_city":
                base = cached_address_parts(record)[1]
            elif key == "shipping_address_1":
                base = cached_address_parts(record)[2][:ADDRESS_DETAIL_LIMIT]
            elif key == "shipping_address_2":
                base = cached_address_parts(record)[2][ADDRESS_DETAIL_LIMIT:]
            elif key == "warning":
                base = cached_warnings(record)
            else:
                base = record.value(key)
            if self.group_candidates.get():
                if key == "product_name":
                    return (base, cached_group_key(record))
                return (cached_group_key(record), base)
            return base

        self.records.sort(key=sort_key, reverse=self.sort_reverse)
        self.records = flatten_record_units(bundled_record_units(self.records))
        self.refresh_tree()
        self.sync_upload_order_to_records()

    def validate_before_export(self) -> bool:
        selected = [record for record in self.records if record.selected and not record.done]
        if not selected:
            messagebox.showwarning(APP_TITLE, "出力対象の行がありません。")
            return False

        issues = []
        critical = []
        for record in selected:
            warnings = validate_record(record, self.postal_db)
            if warnings:
                line = f"{record.value('order_id')} / {record.value('shipping_name')}: " + "、".join(warnings)
                issues.append(line)
                if address_overflow(record):
                    critical.append(line)

        if critical:
            messagebox.showerror(
                APP_TITLE,
                "B2の住所欄に収まらない行があります。住所を短くしてから出力してください。\n\n"
                + "\n".join(critical[:10])
            )
            return False

        if issues:
            return messagebox.askyesno(
                APP_TITLE,
                "住所・郵便番号に確認が必要な行があります。このまま出力しますか？\n\n"
                + "\n".join(issues[:10])
            )
        return True

    def csv_output_target_records(self) -> List[OrderRecord]:
        return [record for record in self.records if record.selected and not record.done]

    def mark_csv_output_done(self, records: List[OrderRecord]) -> int:
        count = 0
        for record in records:
            if not record.done:
                record.done = True
                count += 1
        if count:
            self.refresh_tree()
        return count

    def write_carrier_csvs(self, base_csv_path: Path) -> List[Path]:
        yamato_records = carrier_output_records(self.records, "yamato")
        sagawa_records = carrier_output_records(self.records, "sagawa")
        written: List[Path] = []
        if yamato_records:
            write_b2_csv(base_csv_path, self.records, self.ship_date.get(), self.encoding.get(), self.postal_db)
            written.append(base_csv_path)
        if sagawa_records:
            sagawa_path = base_csv_path if not yamato_records else base_csv_path.with_name(base_csv_path.stem + "_佐川e飛伝III.csv")
            write_sagawa_ehiden3_csv(sagawa_path, self.records, self.ship_date.get(), self.encoding.get(), self.postal_db)
            write_sagawa_manage_map(sagawa_path.with_name(sagawa_path.stem + "_管理番号対応表.csv"), self.records, self.encoding.get())
            written.append(sagawa_path)
        return written

    def output_base(self) -> Path:
        source = Path(self.csv_path.get())
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return source.with_name(f"{source.stem}_B2出荷_{stamp}")

    def export_csv(self) -> Optional[Path]:
        if not self.records:
            messagebox.showwarning(APP_TITLE, "CSVを先に読み込んでください。")
            return None
        if not self.validate_before_export():
            return None
        done_targets = self.csv_output_target_records()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=self.output_base().name + ".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return None
        try:
            written = self.write_carrier_csvs(Path(path))
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return None
        done_count = self.mark_csv_output_done(done_targets)
        self.status.set(f"送り状CSVを出力しました: {', '.join(p.name for p in written)} / 済: {done_count}件")
        return Path(path)

    def export_pdf(self) -> Optional[Path]:
        if not self.records:
            messagebox.showwarning(APP_TITLE, "CSVを先に読み込んでください。")
            return None
        if not self.validate_before_export():
            return None
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=self.output_base().name + ".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return None
        try:
            write_shipping_pdf(Path(path), self.records, self.ship_date.get(), self.postal_db, self.pdf_font_size.get(), self.pdf_font_name.get())
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return None
        open_file(Path(path))
        self.status.set(f"PDFを出力しました: {path}")
        return Path(path)

    def export_both(self) -> None:
        if not self.records:
            messagebox.showwarning(APP_TITLE, "CSVを先に読み込んでください。")
            return
        if not self.validate_before_export():
            return
        done_targets = self.csv_output_target_records()
        base = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=self.output_base().name + ".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not base:
            return
        csv_path = Path(base)
        pdf_path = csv_path.with_suffix(".pdf")
        try:
            written = self.write_carrier_csvs(csv_path)
            write_shipping_pdf(pdf_path, self.records, self.ship_date.get(), self.postal_db, self.pdf_font_size.get(), self.pdf_font_name.get())
            split_count = 0
            split_order_count = 0
            if self.split_b2_by_pdf.get():
                split_count = self.write_split_b2_csvs(csv_path)
                split_order_count = self.write_split_order_csvs(csv_path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        open_file(pdf_path)
        suffix = ""
        if self.split_b2_by_pdf.get():
            suffix = f"\n分割送り状CSV: {split_count}件\n分割注文CSV: {split_order_count}件"
        done_count = self.mark_csv_output_done(done_targets)
        self.status.set(f"出力しました: {', '.join(p.name for p in written)} / {pdf_path.name} / 済: {done_count}件")
        csv_lines = "\n".join(str(p) for p in written)
        messagebox.showinfo(APP_TITLE, f"出力しました。\n{csv_lines}\n{pdf_path}{suffix}\n済に移行: {done_count}件")

    def pdf_page_groups_for_split(self) -> List[List[OrderRecord]]:
        page_groups = split_records_by_pdf_pages(
            self.records,
            self.postal_db,
            self.pdf_font_size.get(),
            self.pdf_font_name.get(),
        )
        pages_per_file = max(1, int(self.split_pdf_pages.get()))
        result = []
        for i in range(0, len(page_groups), pages_per_file):
            group = []
            for page in page_groups[i:i + pages_per_file]:
                group.extend(page)
            result.append(group)
        return result

    def write_split_b2_csvs(self, base_csv_path: Path) -> int:
        groups = self.pdf_page_groups_for_split()
        if not groups:
            return 0
        pages_per_file = max(1, int(self.split_pdf_pages.get()))
        stem = base_csv_path.with_suffix("")
        total_pages = len(split_records_by_pdf_pages(
            self.records,
            self.postal_db,
            self.pdf_font_size.get(),
            self.pdf_font_name.get(),
        ))
        for idx, group in enumerate(groups, start=1):
            start_page = (idx - 1) * pages_per_file + 1
            end_page = min(start_page + pages_per_file - 1, total_pages)
            if pages_per_file == 1:
                name = f"{stem.name}_PDF{start_page}用.csv"
            else:
                name = f"{stem.name}_PDF{start_page}-{min(end_page, start_page + pages_per_file - 1)}用.csv"
            write_b2_csv_for_records(
                base_csv_path.with_name(name),
                group,
                self.ship_date.get(),
                self.encoding.get(),
                self.postal_db,
            )
        return len(groups)

    def write_split_order_csvs(self, base_csv_path: Path) -> int:
        groups = self.pdf_page_groups_for_split()
        if not groups:
            return 0
        fieldnames = list(self.records[0].source.keys()) if self.records else []
        for record in self.records:
            for key in record.source.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            return 0
        pages_per_file = max(1, int(self.split_pdf_pages.get()))
        stem = base_csv_path.with_suffix("")
        total_pages = len(split_records_by_pdf_pages(
            self.records,
            self.postal_db,
            self.pdf_font_size.get(),
            self.pdf_font_name.get(),
        ))
        for idx, group in enumerate(groups, start=1):
            start_page = (idx - 1) * pages_per_file + 1
            end_page = min(start_page + pages_per_file - 1, total_pages)
            if pages_per_file == 1:
                name = f"{stem.name}_PDF{start_page}用_注文CSV.csv"
            else:
                name = f"{stem.name}_PDF{start_page}-{end_page}用_注文CSV.csv"
            path = base_csv_path.with_name(name)
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for record in group:
                    writer.writerow(record.source)
        return len(groups)

def run_cli(csv_file: str, output_dir: Optional[str] = None) -> None:
    source = Path(csv_file)
    apply_invoice_settings(load_invoice_settings(Path(__file__).resolve().parent))
    records = read_orders(source)
    postal_path = Path(__file__).resolve().parent / POSTAL_DATA_DIR / POSTAL_DATA_FILE
    postal_db = PostalCodeDatabase(postal_path) if postal_path.exists() else None
    critical = []
    for record in records:
        warnings = validate_record(record, postal_db)
        if warnings:
            print(f"確認: {record.value('order_id')} / {record.value('shipping_name')}: " + "、".join(warnings))
        if address_overflow(record):
            critical.append(record.value("order_id"))
    if critical:
        raise ValueError("B2の住所欄に収まらない行があります: " + ", ".join(critical[:10]))
    out_dir = Path(output_dir) if output_dir else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = out_dir / f"{source.stem}_B2出荷_{stamp}"
    ship_date = datetime.now().strftime("%Y/%m/%d")
    write_b2_csv(base.with_suffix(".csv"), records, ship_date, "Shift_JIS(cp932)", postal_db)
    write_shipping_pdf(base.with_suffix(".pdf"), records, ship_date, postal_db)
    print(f"CSV: {base.with_suffix('.csv')}")
    print(f"PDF: {base.with_suffix('.pdf')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--csv", help="GUIを使わずに指定CSVからCSV/PDFを作成します。")
    parser.add_argument("--output-dir", help="CLI出力先フォルダ")
    args = parser.parse_args()
    if args.csv:
        run_cli(args.csv, args.output_dir)
        return

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
