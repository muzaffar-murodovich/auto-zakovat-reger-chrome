"""
Zakovat klubi turnirga avtomatik ro'yxatdan o'tish boti.

Sahifani kuzatadi, "Ishtirok etish" tugmasi paydo bo'lishi bilan bosadi,
jamoa va ishtirokchilarni tanlab, "Davom etishi" tugmasiga qadar boradi.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from playwright.sync_api import (
    Page,
    TimeoutError as PWTimeout,
    sync_playwright,
)


CONFIG_PATH = Path(__file__).parent / "config.yaml"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def wait_for_login(page: Page, url: str) -> None:
    """Birinchi safar foydalanuvchidan qo'lda login qilishni so'raydi."""
    page.goto(url, wait_until="domcontentloaded")
    print()
    print("=" * 60)
    print("  Agar saytga hali kirmagan bo'lsangiz, brauzerda login qiling.")
    print("  Tayyor bo'lsangiz, shu terminal'da Enter bosing.")
    print("=" * 60)
    try:
        input()
    except EOFError:
        pass


def find_participate_button(page: Page, text: str):
    """\"Ishtirok etish\" tugmasini izlaydi. Topilmasa None."""
    btn = page.get_by_role("button", name=text).first
    try:
        if btn.is_visible(timeout=1000):
            return btn
    except PWTimeout:
        pass
    except Exception:
        pass
    # Fallback: matn bo'yicha izlash
    alt = page.locator(f"text={text}").first
    try:
        if alt.is_visible(timeout=500):
            return alt
    except Exception:
        pass
    return None


def poll_for_button(page: Page, url: str, text: str, interval: float):
    """Tugma paydo bo'lguncha sahifani qayta yuklaydi."""
    log(f"Polling boshlandi. URL: {url}")
    log(f"Tugma matni: '{text}', interval: {interval}s")
    attempts = 0
    while True:
        attempts += 1
        try:
            btn = find_participate_button(page, text)
            if btn is not None:
                log(f"TUGMA TOPILDI (urinish #{attempts})! Bosilmoqda...")
                return btn
            else:
                log(f"#{attempts}: tugma yo'q, qayta yuklayapman...")
        except Exception as exc:
            log(f"#{attempts}: xato — {exc!r}, davom etyapman")

        time.sleep(interval)
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception as exc:
            log(f"Reload xato: {exc!r} — kutaman va qayta urinaman")
            time.sleep(interval)


def select_team(page: Page, modal_title: str) -> None:
    """\"Turnirda ro'yxatdan o'tish\" modal'ida birinchi jamoani tanlaydi."""
    log(f"Jamoa modal'i kutilmoqda: '{modal_title}'")
    page.locator(f"text={modal_title}").first.wait_for(state="visible", timeout=10000)
    log("Modal ochildi. Birinchi jamoa qatorini tanlayapman.")

    # Modal ichidagi birinchi clickable jamoa qatorini topishga harakat qilamiz.
    # Avval radio/checkbox, keyin button/role, keyin matn-asosli qator.
    candidates = [
        page.get_by_role("radio").first,
        page.locator("[role='radio']").first,
        page.locator("input[type='radio']").first,
        page.locator("input[type='checkbox']").first,
    ]
    for cand in candidates:
        try:
            if cand.is_visible(timeout=500):
                cand.click()
                log("Jamoa tanlandi (radio/checkbox).")
                return
        except Exception:
            continue

    # Fallback: modal ichidagi birinchi katta clickable elementni bosamiz
    # (Baurlar yozuvi bor qator).
    try:
        page.locator("text=Baurlar").first.click(timeout=3000)
        log("Jamoa tanlandi (matn bo'yicha 'Baurlar').")
        return
    except Exception:
        pass

    raise RuntimeError("Jamoa qatorini tanlay olmadim — selektor moslashmadi.")


def select_participants_and_continue(
    page: Page,
    modal_title: str,
    bilimdonlar_heading: str,
    row_selector: str,
    addable_class: str,
    continue_text: str,
) -> None:
    """Ishtirokchilar modal'ida barcha bilimdonlarni qo'shadi va Davom etishi'ni bosadi."""
    log(f"Ishtirokchilar modal'i kutilmoqda: '{modal_title}'")
    page.locator(f"text={modal_title}").first.wait_for(state="visible", timeout=10000)
    log("Modal ochildi. Bilimdonlar bo'limi yuklanishini kutaman...")

    # "Bilimdonlar" sarlavhasidan keyin keluvchi ".income-person__main" bo'limini topamiz.
    # HTML: <h2 class="income-person__main-title">Bilimdonlar</h2>
    #       <div class="income-person__main-list"> <div class="income-person__main-player add">...</div> ... </div>
    bilimdonlar_section = page.locator(
        ".income-person__main",
        has=page.locator(f".income-person__main-title:has-text('{bilimdonlar_heading}')"),
    ).first

    # Bilimdonlar API'dan kechikib yuklanishi mumkin. Birinchi qator paydo
    # bo'lishini 15 sekundgacha kutamiz.
    try:
        bilimdonlar_section.locator(
            f"{row_selector}.{addable_class}"
        ).first.wait_for(state="visible", timeout=15000)
        log("Birinchi bilimdon paydo bo'ldi.")
    except Exception as exc:
        log(f"OGOHLANTIRISH: bilimdonlar yuklanmadi yoki bo'sh ({exc!r}).")

    # Qisqa qo'shimcha pauza — qolgan elementlar ham render bo'lib ulgursin
    page.wait_for_timeout(400)

    # Har bosishdan keyin DOM o'zgaradi (class 'add' olib tashlanishi mumkin),
    # shuning uchun har safar qayta izlaymiz.
    max_clicks = 10
    clicks = 0
    while clicks < max_clicks:
        # Tanlanmagan (hali "add" class'i bor) qatorni izlaymiz
        addable_rows = bilimdonlar_section.locator(
            f"{row_selector}.{addable_class}"
        )
        count = addable_rows.count()
        if count == 0:
            log(f"Qo'shiladigan bilimdon qolmadi. Jami {clicks} ta tanlandi.")
            break

        target = addable_rows.first
        try:
            target.scroll_into_view_if_needed(timeout=2000)
            target.click(timeout=3000)
            clicks += 1
            log(f"Bilimdon qo'shildi (#{clicks}). Qolgan: {count - 1}")
            page.wait_for_timeout(300)
        except Exception as exc:
            log(f"Qator bosishda xato: {exc!r} — to'xtayman")
            break

    click_continue(page, continue_text)


def click_continue(page: Page, continue_text: str) -> None:
    """\"Davom etishi\" tugmasi faollashishini kutib, bosadi."""
    log(f"'{continue_text}' tugmasini bosishga urinish (faollashishini kutaman)...")
    cont = page.get_by_role("button", name=continue_text).first
    try:
        cont.wait_for(state="visible", timeout=5000)
        # Disabled holatdan chiqishini polling bilan kutamiz
        for _ in range(20):  # 10 sekund
            try:
                if cont.is_enabled(timeout=300):
                    break
            except Exception:
                pass
            page.wait_for_timeout(500)
        # Tugma faollashgach, qisqa pauza — animatsiya/overlay tugashi uchun
        page.wait_for_timeout(400)
        try:
            cont.click(timeout=3000)
            log(f"'{continue_text}' bosildi!")
            return
        except Exception as exc:
            log(f"Oddiy click ishlamadi ({exc!r}). Force/JS click bilan urinaman.")
        # Fallback 1: force click — overlay xalalini e'tiborsiz qoldiradi
        try:
            cont.click(force=True, timeout=3000)
            log(f"'{continue_text}' bosildi (force).")
            return
        except Exception as exc:
            log(f"Force click ham ishlamadi ({exc!r}). JS click bilan urinaman.")
        # Fallback 2: JS click
        cont.evaluate("el => el.click()")
        log(f"'{continue_text}' bosildi (JS).")
    except Exception as exc:
        log(f"'{continue_text}' tugmasini bosib bo'lmadi: {exc!r}")
        raise


def click_via_mouse(page: Page, locator, label: str) -> bool:
    """Element markaziga real mouse coordinate orqali click qiladi.

    Bu usul `force=True`dan farqli ravishda haqiqiy mouse pointer harakati
    yuboradi (mousemove + mousedown + mouseup) — bu eng yaqin "real user click"
    simulyatsiyasi. Lekin u ham pointer-event intercept'larni hisobga oladi,
    shuning uchun avval scroll qilib, elementni eng yuqori qatlamga keltiramiz.
    """
    try:
        box = locator.bounding_box(timeout=2000)
        if not box:
            log(f"{label}: bounding_box null")
            return False
        x = box["x"] + box["width"] / 2
        y = box["y"] + box["height"] / 2
        page.mouse.click(x, y)
        log(f"{label}: mouse click ({x:.0f}, {y:.0f})")
        return True
    except Exception as exc:
        log(f"{label}: mouse click xato — {exc!r}")
        return False


def select_club_and_continue(page: Page, continue_text: str) -> None:
    """Klub tanlash modal'ida 1-klubni tanlaydi va Davom etishi'ni bosadi.

    Sayt modal'larni stack qiladi (jamoa + ishtirokchilar + klub modal'lari
    bir vaqtda ochiq). Klub modal'i — eng ustki (`.modal.open` ro'yxatidagi
    oxirgi element). Kartalarni bosish uchun real mouse coordinate ishlatamiz
    chunki force/JS click sayt React handler'ini ishga tushirmaydi.
    """
    log("Klub modal'i kutilmoqda...")
    modal = page.locator(".modal.open").last
    first_card = modal.locator(".my-teams-card").first
    first_card.wait_for(state="visible", timeout=15000)

    try:
        page.bring_to_front()
    except Exception:
        pass

    page.wait_for_timeout(500)
    first_card.scroll_into_view_if_needed(timeout=2000)
    page.wait_for_timeout(400)
    log("Birinchi klubni tanlayapman...")
    click_via_mouse(page, first_card, "Klub karta")
    page.wait_for_timeout(800)

    cont = modal.get_by_role("button", name=continue_text).first
    cont.wait_for(state="visible", timeout=10000)
    cont.scroll_into_view_if_needed(timeout=2000)
    page.wait_for_timeout(400)
    log("'Davom etishi'ni bosaman...")
    click_via_mouse(page, cont, "Davom etishi")
    page.wait_for_timeout(1500)


def main() -> int:
    cfg = load_config()
    url = cfg["tournament_url_template"].format(tournament_id=cfg["tournament_id"])
    poll_interval = float(cfg["poll_interval_seconds"])
    headless = bool(cfg["headless"])
    user_data_dir = str(Path(cfg["user_data_dir"]).resolve())
    sel = cfg["selectors"]

    Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    log("Brauzer ishga tushirilmoqda...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            viewport={"width": 1400, "height": 900},
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Birinchi safar bo'lsa, login qilishni so'rashning oddiy yo'li:
        # foydalanuvchidan tasdiqlashni so'raymiz. Agar avtomatik ravishda
        # sahifa profiliga kirgan bo'lsa, foydalanuvchi shunchaki Enter bosadi.
        wait_for_login(page, url)

        # Polling
        try:
            btn = poll_for_button(
                page, url, sel["participate_button_text"], poll_interval
            )
            btn.click()
            log("Ishtirok etish tugmasi bosildi.")

            select_team(page, sel["team_modal_title"])

            # Ko'pgina hollarda jamoa tanlangach avtomatik keyingi modal'ga o'tadi.
            # Bo'lmasa, modal ichida "keyingi" tugmasi bo'lishi mumkin — kuzatib aniqlaymiz.
            select_participants_and_continue(
                page,
                sel["participants_modal_title"],
                sel["bilimdonlar_heading_text"],
                sel["participant_row_selector"],
                sel["participant_addable_class"],
                sel["continue_button_text"],
            )

            select_club_and_continue(page, sel["continue_button_text"])

            print()
            print("=" * 60)
            print("  TAYYOR! Turnirga ro'yxatdan o'tish yakunlandi.")
            print("  Bilimdonlarga takliflar yuborildi.")
            print("  Brauzerni yopish uchun shu terminal'da Enter bosing.")
            print("=" * 60)
            try:
                input()
            except EOFError:
                pass

        except KeyboardInterrupt:
            log("Ctrl+C — to'xtatilyapti.")
        except Exception as exc:
            log(f"XATO: {exc!r}")
            print()
            print("Brauzer ochiq qoldirildi — qo'lda davom ettirishingiz mumkin.")
            print("Yopish uchun Enter bosing.")
            try:
                input()
            except EOFError:
                pass

        context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
