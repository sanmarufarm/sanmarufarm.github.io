"""농원정보.yml + template/ 로 홈페이지(_site 폴더)를 만듭니다.

GitHub에서는 저장할 때마다 자동으로 실행됩니다.
내 컴퓨터에서 확인하려면:  pip install pyyaml jinja2 pillow  →  python build.py
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
IMG = ROOT / "images"
SEASONS = [("봄", [3, 4, 5]), ("여름", [6, 7, 8]), ("가을", [9, 10, 11]), ("겨울", [12, 1, 2])]
YEAR_ROUND = ("연중", "사계절", "항상")

problems = []
notes = []
used_photos = set()


def need(d, key, where):
    v = d.get(key) if isinstance(d, dict) else None
    if v in (None, ""):
        problems.append(f"'{where}'에 '{key}' 값이 비어 있습니다.")
    return v


def photo(name, where):
    """사진이 images 폴더에 있으면 이름을, 없으면 None(글자 카드로 표시)을 돌려줍니다."""
    if not name:
        return None
    name = str(name).strip()
    if (IMG / name).exists():
        used_photos.add(name)
        return name
    notes.append(f"'{where}'의 사진 '{name}'이(가) images 폴더에 없어 사진 없이 표시합니다.")
    return None


def month_num(v, where):
    try:
        m = int(v)
        if 1 <= m <= 12:
            return m
    except (TypeError, ValueError):
        pass
    problems.append(f"'{where}'의 월 값 '{v}'은(는) 1~12 숫자이거나 '연중'이어야 합니다.")
    return 1


def lines(text):
    return [t.strip() for t in str(text or "").strip().splitlines() if t.strip()]


def copy_images():
    """사진을 _site/images 로 복사하면서, 휴대폰 사진처럼 큰 사진은 줄입니다."""
    dst = OUT / "images"
    dst.mkdir(parents=True)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], check=True)
            from PIL import Image, ImageOps
        except Exception:
            Image = None
    for f in sorted(IMG.iterdir()):
        if not f.is_file() or f.name not in used_photos:   # 홈페이지에 쓰는 사진만 올림
            continue
        if Image and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.stat().st_size > 400_000:
            try:
                im = ImageOps.exif_transpose(Image.open(f))
                im.thumbnail((1600, 1600))
                if f.suffix.lower() in (".jpg", ".jpeg"):
                    im.convert("RGB").save(dst / f.name, quality=82, optimize=True, progressive=True)
                else:
                    im.save(dst / f.name, optimize=True)
                continue
            except Exception as e:
                notes.append(f"사진 '{f.name}' 줄이기 실패({e}) — 원본 그대로 올립니다.")
        shutil.copy(f, dst / f.name)


def main():
    try:
        data = yaml.safe_load((ROOT / "농원정보.yml").read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"{mark.line + 1}번째 줄 근처" if mark else "어딘가"
        sys.exit(f"\n[오류] 농원정보.yml {where}의 형식이 맞지 않습니다.\n"
                 "들여쓰기(줄 앞 띄어쓰기)나 콜론(:) 뒤 띄어쓰기를 확인하세요.\n")

    d = data
    name = need(d, "농원이름", "기본 정보")
    url = str(need(d, "홈페이지주소", "기본 정보") or "").rstrip("/") + "/"
    addr = need(d, "주소", "기본 정보")
    tel = str(need(d, "전화번호", "기본 정보") or "")
    tel_digits = "".join(c for c in tel if c.isdigit())

    def fill(text):
        return str(text or "").replace("{전화번호}", tel).replace("{주소}", str(addr))

    # 판매 품목
    crops = []
    for i, c in enumerate(d.get("작물") or [], 1):
        where = f"작물 {i}번째"
        if str(c.get("숨기기", "")).strip() in ("예", "yes", "true", "True"):
            continue
        cname = str(need(c, "이름", where))
        where = f"작물 '{cname}'"
        start = str(c.get("판매시작", "")).strip()
        if start in YEAR_ROUND:
            months, when, all_year = list(range(1, 13)), "연중", True
        else:
            s, e = month_num(c.get("판매시작"), where), month_num(c.get("판매끝"), where)
            months = [(s - 1 + k) % 12 + 1 for k in range((e - s) % 12 + 1)]
            when = f"{s}월" if s == e else (f"{s}월 – {e}월" if s < e else f"{s}월 – 이듬해 {e}월")
            all_year = False
        crops.append({"name": cname, "season": months, "when": when, "all_year": all_year,
                      "group": str(c.get("분류") or "").strip(),
                      "photo": photo(c.get("사진"), where), "desc": fill(need(c, "설명", where))})
    if not crops:
        problems.append("'작물' 목록이 비어 있습니다.")

    hero = dict(d.get("첫화면") or {})
    hero_photos = []
    for i, p in enumerate(hero.get("사진") or [], 1):
        if photo(p.get("파일"), f"첫화면 사진 {i}번째"):
            hero_photos.append({"file": p.get("파일"), "alt": p.get("설명", "")})
    if not hero_photos:
        problems.append("'첫화면' 사진이 하나도 없습니다. images 폴더에 있는 사진 이름을 적어 주세요.")
    about = dict(d.get("농원소개") or {})
    about_photo = photo(about.get("사진"), "농원소개")
    diary = []
    for p in d.get("농장일기") or []:
        diary.append({"title": p.get("제목"), "when": p.get("때"), "text": p.get("내용"),
                      "photo": photo(p.get("사진"), f"농장일기 '{p.get('제목')}'")})

    seasonal = [c for c in crops if not c["all_year"]]
    year_round = [c for c in crops if c["all_year"]]
    schedule = ", ".join(f"{c['name']} {c['when']}" for c in seasonal)
    if year_round:
        schedule += ("" if not schedule else ", ") + "·".join(c["name"] for c in year_round) + "은(는) 연중"
    faq = []
    for q in d.get("자주묻는질문") or []:
        a = str(q.get("답", "")).strip()
        if a == "자동":
            a = f"{schedule} 판매합니다. 그해 날씨와 수확량에 따라 조금씩 달라질 수 있습니다."
        faq.append({"q": fill(q.get("질문")), "a": fill(a)})

    if problems:
        sys.exit("\n[오류] 농원정보.yml을 확인해 주세요:\n - " + "\n - ".join(problems) + "\n")

    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    cur = now.month
    on_sale = [c for c in seasonal if cur in c["season"]]
    nxt = ""
    for k in range(1, 13):
        mm = (cur - 1 + k) % 12 + 1
        starting = [c["name"] for c in seasonal if c["season"][0] == mm and cur not in c["season"]]
        if starting:
            nxt = f"{mm}월 " + ", ".join(starting)
            break

    calendar = [{"name": sn, "range": f"{ms[0]} – {ms[-1]}월",
                 "months": [{"m": m, "crops": [c["name"].split("(")[0].strip() for c in seasonal if m in c["season"]]} for m in ms]}
                for sn, ms in SEASONS]

    groups = []
    for c in crops:
        grp = next((x for x in groups if x["name"] == c["group"]), None)
        if grp is None:
            grp = {"name": c["group"], "items": []}
            groups.append(grp)
        grp["items"].append(c)

    crop_names = [c["name"] for c in crops]
    short = lambda n: n.split("(")[0].strip()
    keywords = ["강화 농산물", "강화도 농산물"] + [f"강화 {short(n)}" for n in crop_names] + \
               ["강화 직거래", "강화 농원"] + [w for w in str(addr).split() if w.endswith(("면", "리"))] + [name]
    top3 = "·".join(str(x) for x in (d.get("대표작물") or [short(n) for n in crop_names[:3]]))
    first_hero = hero_photos[0]["file"]

    ld_business = {
        "@context": "https://schema.org", "@type": "LocalBusiness",
        "name": name, "alternateName": f"강화 {name}", "url": url,
        "description": f"{addr}에서 {', '.join(short(n) for n in crop_names)} 등을 직접 기르고 만들어 농원 방문 판매와 택배로 판매하는 가족 농원. 대량 주문·납품 상담 가능.",
        "telephone": tel,
        "address": {"@type": "PostalAddress", "streetAddress": " ".join(str(addr).split()[2:]),
                    "addressLocality": str(addr).split()[1] if len(str(addr).split()) > 1 else "",
                    "addressRegion": str(addr).split()[0], "addressCountry": "KR"},
        "areaServed": "대한민국",
        "image": url + "images/" + first_hero,
        "knowsAbout": [f"강화 {short(n)}" for n in crop_names],
        "makesOffer": [{"@type": "Offer", "itemOffered": {"@type": "Product", "name": f"강화 {c['name']}"},
                        "description": f"판매 시기 {c['when']}. {c['desc']}"} for c in crops],
    }
    if d.get("블로그주소"):
        ld_business["sameAs"] = [d["블로그주소"]]
    ld_faq = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": f["q"],
                              "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}

    # 사진 출처: 실제로 쓰는 사진만 표시
    credits = []
    for item in d.get("사진출처") or []:
        if isinstance(item, dict):
            if item.get("파일") and item["파일"] not in used_photos:
                continue
            credits.append({"text": str(item.get("출처", "")).strip(), "link": str(item.get("링크", "")).strip()})
        else:
            text, _, link = str(item).partition("|")
            credits.append({"text": text.strip(), "link": link.strip()})

    ctx = dict(
        name=name, url=url, addr=addr, tel=tel, tel_digits=tel_digits,
        logo_sub=d.get("작은로고글자", ""),
        naver=str(d.get("네이버인증코드") or "").strip(), google=str(d.get("구글인증코드") or "").strip(),
        blog=str(d.get("블로그주소") or "").strip(),
        hero=hero, hero_photos=hero_photos, hero_title=lines(hero.get("제목")), first_hero=first_hero,
        about=about, about_photo=about_photo or first_hero, about_title=lines(about.get("제목")),
        crops=crops, groups=groups, on_sale=on_sale, year_round=year_round,
        cur=cur, nxt=nxt, calendar=calendar,
        empty_month=d.get("판매없는달문구", ""), empty_now=lines(d.get("판매없는달안내")),
        ways=d.get("구매방법") or [], order_note=fill(d.get("주문안내")), bulk_note=fill(d.get("대량문의")),
        diary=diary, faq=faq, credits=credits,
        keywords=", ".join(dict.fromkeys(keywords)), top3=top3,
        crops_js=json.dumps([{"name": c["name"], "season": c["season"], "when": c["when"], "all_year": c["all_year"],
                              "photo": c["photo"], "desc": c["desc"]} for c in crops], ensure_ascii=False),
        ld_business=json.dumps(ld_business, ensure_ascii=False),
        ld_faq=json.dumps(ld_faq, ensure_ascii=False),
        today=now.strftime("%Y-%m-%d"), year=now.year,
        sms_body=str(d.get("문자양식") or "").strip(),
        ways_text=", ".join(w.get("제목", "") for w in d.get("구매방법") or []),
    )

    env = Environment(loader=FileSystemLoader(ROOT / "template"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    copy_images()
    shutil.copy(ROOT / "template" / "style.css", OUT / "style.css")
    (OUT / "index.html").write_text(env.get_template("index.html").render(**ctx), encoding="utf-8")
    (OUT / "llms.txt").write_text(env.get_template("llms.txt").render(**ctx), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {url}sitemap.xml\n", encoding="utf-8")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{url}</loc><lastmod>{ctx["today"]}</lastmod><changefreq>monthly</changefreq></url>\n'
        '</urlset>\n', encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    for n in notes:
        print("[참고]", n)
    print(f"완료: 품목 {len(crops)}개(연중 {len(year_round)}개), 이달({cur}월) 판매 {len(on_sale)}개 → _site/")


if __name__ == "__main__":
    main()
