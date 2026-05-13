import json
from core.settings import settings
from core.utils.dac import dac_set_voltage_for_level

class DimmingController:
    # Logaritmik parlaklık skalası (insan gözü ışığı logaritmik algılar)
    # 0: kapalı, 1: minimum, sonrası logaritmik artış ile 100'e ulaşır
    LEVELS = {
        0: 0,
        1: 1,
        2: 2,
        3: 4,
        4: 7,
        5: 13,
        6: 22,
        7: 37,
        8: 61,
        9: 100
    }

    MODES = ["day", "dusk", "night"]

    def __init__(self):
        self._load_from_file()

    def _load_from_file(self):
        try:
            with open(settings.DIMMING_FILE, "r") as f:
                data = json.load(f)
                self.current_level = data.get("level", 5)
                self.mode = data.get("mode", "day")
        except (FileNotFoundError, json.JSONDecodeError):
            self.current_level = 5
            self.mode = "day"
            self._save_to_file()

    def _save_to_file(self):
        brightness = self.LEVELS.get(self.current_level, 13)
        
        # Level 0 için özel durum: brightness 1 (minimum ışık) + DAC voltaj kesme
        if self.current_level == 0:
            actual_brightness = 1
        else:
            actual_brightness = brightness
        
        data = {
            "level": self.current_level,
            "brightness": brightness,
            "mode": self.mode
        }
        
        # JSON dosyasına yaz (backward compatibility)
        with open(settings.DIMMING_FILE, "w") as f:
            json.dump(data, f, indent=2)
        
        # Direkt sistem backlight dosyasına yaz
        try:
            with open("/sys/class/backlight/backlight/brightness", "w") as f:
                f.write(str(actual_brightness))
        except (FileNotFoundError, PermissionError) as e:
            # Docker'da mount edilmemişse veya permission yoksa sessizce geç
            if settings.DEBUG:
                print(f"[DIMMING] Could not write to backlight: {e}")
        
        # DAC voltaj kontrolü
        try:
            dac_set_voltage_for_level(self.current_level)
        except Exception as e:
            if settings.DEBUG:
                print(f"[DIMMING] DAC control error: {e}")

    def level_up(self):
        if self.current_level >= max(self.LEVELS.keys()):
            return False
        self.current_level += 1
        self._save_to_file()
        return True

    def level_down(self):
        if self.current_level <= min(self.LEVELS.keys()):
            return False
        self.current_level -= 1
        self._save_to_file()
        return True

    def set_level(self, level: int):
        min_level = min(self.LEVELS.keys())
        max_level = max(self.LEVELS.keys())
        if level < min_level or level > max_level:
            return False
        self.current_level = level
        self._save_to_file()
        return True

    def set_mode(self, mode: str):
        if mode not in self.MODES:
            return False
        self.mode = mode
        self._save_to_file()
        return True

    def get_current_level(self):
        return self.current_level

    def get_current_brightness(self):
        return self.LEVELS.get(self.current_level, 13)

    def get_mode(self):
        return self.mode

    def get_ranges(self):
        return min(self.LEVELS.keys()), max(self.LEVELS.keys())

    def get_status(self):
        min_level, max_level = self.get_ranges()
        return {
            "level": self.current_level,
            "brightness": self.get_current_brightness(),
            "mode": self.mode,
            "min": min_level,
            "max": max_level,
            "modes": self.MODES
        }

dimming_controller = DimmingController()

