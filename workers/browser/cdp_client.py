"""
workers/browser/cdp_client.py
─────────────────────────────
مدير اتصال Playwright عبر Chrome Remote Debugging (Port 9222).
مبني بنمط Singleton آمن يمنع إغلاق المتصفح عن طريق الخطأ، ويتيح إعادة استخدام
الاتصال عبر عدة مهام وأدوات بسلاسة.
"""

import logging
import socket
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from config.settings import CHROME_CDP_PORT, CHROME_CDP_URL

logger = logging.getLogger("CDPClient")


def is_cdp_port_open(host: str = "127.0.0.1", port: int = CHROME_CDP_PORT) -> bool:
    """فحص سريع للتأكد من أن Chrome شغال بوضع Remote Debugging."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.5)
        return sock.connect_ex((host, port)) == 0


class CDPSessionManager:
    """مدير الاتصال الدائم بمتصفح Chrome المفتوح."""

    _instance: Optional["CDPSessionManager"] = None

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @classmethod
    def get_instance(cls) -> "CDPSessionManager":
        if cls._instance is None:
            cls._instance = CDPSessionManager()
        return cls._instance

    def connect(self) -> BrowserContext:
        """الاتصال بـ Chrome إذا لم يكن متصلاً بالفعل."""
        if not is_cdp_port_open():
            raise ConnectionError(
                f"❌ متصفح Chrome غير شغال على المنفذ {CHROME_CDP_PORT}!\n"
                f"شغّل Chrome أولاً بالأمر التالي:\n"
                f'chrome.exe --remote-debugging-port={CHROME_CDP_PORT} --user-data-dir="C:\\Users\\shaher\\AppData\\Local\\Google\\Chrome\\User Data"'
            )

        if self._browser is None or not self._browser.is_connected():
            logger.info(f"جاري الاتصال بمتصفح Chrome عبر CDP: {CHROME_CDP_URL}...")
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(CHROME_CDP_URL)
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
            else:
                self._context = self._browser.new_context()

        return self._context

    def new_page(self) -> Page:
        """فتح تاب جديدة معزولة لأداء مهمة معينة."""
        context = self.connect()
        page = context.new_page()
        # تقليل وقت المهلة الافتراضي للـ selectors لـ 15 ثانية بدل 30
        page.set_default_timeout(15000)
        return page

    def close_all(self):
        """إغلاق اتصال الـ client بدون إغلاق المتصفح الفعلي للمستخدم."""
        if self._playwright:
            try:
                if self._browser:
                    # لا نستدعي browser.close() حتى لا نقفل متصفح المستخدم
                    pass
                self._playwright.stop()
            except Exception as exc:
                logger.debug(f"استثناء أثناء تفكيك Playwright: {exc}")
            finally:
                self._playwright = None
                self._browser = None
                self._context = None


def get_cdp_manager() -> CDPSessionManager:
    return CDPSessionManager.get_instance()
