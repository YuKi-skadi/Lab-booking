import json
import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict
from .config import settings

SETTINGS_FILE = os.path.join(settings.json_data_dir, "settings.json")

DEFAULT_SETTINGS = {
    "classrooms": [
        "101实验室", "102实验室", "201机房", "202机房",
        "301多媒体教室", "302多媒体教室", "401研讨室", "402研讨室"
    ],
    "time_slots": [
        {"slot": "08:00-09:35", "remark": "第一课时"},
        {"slot": "09:50-11:25", "remark": "第二课时"},
        {"slot": "11:40-13:15", "remark": "第三课时"},
        {"slot": "13:30-15:05", "remark": "第四课时"},
        {"slot": "15:20-16:55", "remark": "第五课时"},
        {"slot": "17:10-18:45", "remark": "第六课时"},
    ],
    "majors": [
        "计算机科学与技术", "软件工程", "电子信息工程",
        "通信工程", "机械工程", "自动化", "电气工程",
        "材料科学与工程", "化学工程", "生物工程",
        "数学与应用数学", "物理学", "应用化学",
        "工商管理", "会计学", "金融学"
    ],
    "form_fields": {
        "student_name": {"required": True, "label": "姓名", "type": "text", "order": 1},
        "student_id": {"required": True, "label": "学号", "type": "text", "order": 2},
        "major": {"required": True, "label": "专业", "type": "select", "order": 3},
        "supervisor": {"required": True, "label": "指导教师", "type": "text", "order": 4},
        "phone": {"required": False, "label": "手机号", "type": "text", "order": 5},
        "classroom": {"required": True, "label": "借用教室", "type": "room_select", "order": 6},
        "booking_date": {"required": True, "label": "借用日期", "type": "date", "order": 7},
        "time_slot": {"required": True, "label": "借用时间", "type": "time_select", "order": 8},
        "purpose": {"required": False, "label": "借用用途", "type": "textarea", "order": 9},
    },
    "success_message": "预约已提交，请按照学校/单位规定流程确认预约并办理正式手续。",
    "admin_password": settings.admin_password,
    "subtitle": {
        "text": "请填写以下信息完成实验室预约",
        "fontSize": "16px",
        "fontWeight": "400",
        "fontStyle": "normal",
        "color": "#ffffff",
    },
    "notice_lines": [
        "请及时到办公室核实能否正式预约",
        "办理正式手续后方可使用教室",
    ],
}


class SettingsManager:
    def __init__(self):
        self._data: dict = None
        os.makedirs(settings.json_data_dir, exist_ok=True)

    def _ensure_loaded(self):
        if self._data is None:
            self.load()

    def load(self) -> dict:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            self._data = {**DEFAULT_SETTINGS, **stored}
        else:
            self._data = dict(DEFAULT_SETTINGS)
            self.save()
        return self._data

    def save(self):
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_FILE)

    def get_all(self) -> dict:
        self._ensure_loaded()
        return dict(self._data)

    def get(self, key: str, default=None):
        self._ensure_loaded()
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._ensure_loaded()
        self._data[key] = value
        self.save()

    def update(self, updates: dict):
        self._ensure_loaded()
        self._data.update(updates)
        self.save()

    @property
    def classrooms(self) -> List[str]:
        return self.get("classrooms", DEFAULT_SETTINGS["classrooms"])

    @property
    def time_slots_raw(self) -> list:
        return self.get("time_slots", DEFAULT_SETTINGS["time_slots"])

    @property
    def time_slots(self) -> List[dict]:
        raw = self.time_slots_raw
        result = []
        for item in raw:
            if isinstance(item, str):
                parts = item.split("-")
                if len(parts) == 2:
                    result.append({"slot": item, "start": parts[0].strip(), "end": parts[1].strip(), "remark": ""})
            elif isinstance(item, dict):
                slot = item.get("slot", "")
                parts = slot.split("-")
                if len(parts) == 2:
                    result.append({
                        "slot": slot,
                        "start": parts[0].strip(),
                        "end": parts[1].strip(),
                        "remark": item.get("remark", ""),
                    })
        return result

    @property
    def parsed_time_slots(self) -> List[dict]:
        return self.time_slots

    @property
    def subtitle(self) -> dict:
        default = DEFAULT_SETTINGS["subtitle"]
        stored = self.get("subtitle", {})
        return {**default, **stored}

    @property
    def majors(self) -> List[str]:
        return self.get("majors", DEFAULT_SETTINGS["majors"])

    @property
    def form_fields(self) -> dict:
        return self.get("form_fields", DEFAULT_SETTINGS["form_fields"])

    @property
    def success_message(self) -> str:
        return self.get("success_message", DEFAULT_SETTINGS["success_message"])

    @property
    def admin_password(self) -> str:
        return self.get("admin_password", settings.admin_password)

    @property
    def notice_lines(self) -> List[str]:
        return self.get("notice_lines", DEFAULT_SETTINGS["notice_lines"])

    def check_admin_password(self, password: str) -> bool:
        return password == self.admin_password



_manager_instance: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SettingsManager()
        _manager_instance.load()
    return _manager_instance
