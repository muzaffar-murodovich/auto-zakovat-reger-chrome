> **⚠️ ARXIV (2026-07-06 dan).** Bu loyiha endi ishlatilmaydi. Avtomatik
> ro'yxatdan o'tish `zakovat-quiz-checker-bot` ichida to'g'ridan-to'g'ri API
> orqali (`POST /v1/user/request`, brauzersiz) bajariladi — u serverda 24/7
> ishlaydi, quiz ochilganda Baurlar jamoasini o'zi yozadi. zk-auto faqat
> qo'lda zaxira variant sifatida saqlanib turibdi.

# zk-auto — Zakovat klubi turnirga avtomatik ro'yxatdan o'tish

Belgilangan turnir sahifasini (`https://zakovatklubi.uz/tournaments/{id}`) doimiy kuzatib, "Ishtirok etish" tugmasi paydo bo'lishi bilanoq uni bosib, jamoa va ishtirokchilarni tanlab, "Davom etishi" tugmasiga qadar avtomatik o'tadi.

## O'rnatish

```bash
# 1. Virtual muhit yaratish
python3 -m venv venv
source venv/bin/activate

# 2. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 3. Chromium brauzerini o'rnatish
playwright install chromium
```

## Sozlash

`config.yaml` faylida `tournament_id` ni o'zgartiring:

```yaml
tournament_id: 18089
```

## Ishga tushirish

```bash
source venv/bin/activate
python bot.py
```

**Birinchi marta:** brauzer ochiladi, saytga qo'lda login qiling va terminal'ga Enter bosing. Cookie `./user-data/` ichida saqlanadi.

**Keyingi safar:** login holatda avtomatik davom etadi.

## Mantiq

1. Tournament URL'iga o'tadi
2. Har 2.5 sekundda sahifani qayta yuklab, "Ishtirok etish" tugmasini izlaydi
3. Tugma topilsa — bosadi
4. "Turnirda ro'yxatdan o'tish" modal'ida birinchi jamoani tanlaydi
5. "Ishtirokchilarni tanlang" modal'ida barcha bilimdonlarni `+` orqali qo'shadi
6. "Davom etishi" tugmasini bosadi
7. To'xtaydi — qolganini qo'lda yakunlaysiz

Ctrl+C bilan istalgan paytda to'xtatish mumkin.
