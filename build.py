"""농원정보.yml + template/ 로 홈페이지(_site 폴더)를 만듭니다.

GitHub에서는 저장할 때마다 자동으로 실행됩니다.
내 컴퓨터에서 확인하려면:  pip install pyyaml jinja2  →  python build.py
"""
import datetime
import json
import shutil
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
IMG = ROOT / "images"
SEASONS = [("봄", [3, 4, 5]), ("여름", [6, 7, 8]), ("가을", [9, 10, 11]), ("겨울", [12, 1, 2])]

problems = []


def need(d, key, where):
    v = d.get(key) if isinstance(d, dict) else None
    if v in (None, ""):
        problems.append(f"'{where}'에 '{key}' 값이 비어 있습니다.")
    return v


def check_photo(name, where):
    if name and not (IMG / name).exists():
        problems.append(f"'{where}'의 사진 '{name}'이(가) images 폴더에 없습니다. 파일 이름(대소문자·확장자)을 확인하세요.")


def month_num(v, where):
    try:
        m = int(v)
        if 1 <= m <= 12:
            return m
    except (TypeError, ValueError):
        pass
    problems.append(f"'{where}'의 월 값 '{v}'은(는) 1~12 숫자여야 합니다.")
    return 1


def lines(text):
    return [t.strip() for t in str(text or "").strip().splitlines() if t.strip()]


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

    # 작물
    crops = []
    for i, c in enumerate(d.get("작물") or [], 1):
        where = f"작물 {i}번째"
        if str(c.get("숨기기", "")).strip() in ("예", "yes", "true", "True"):
            continue
        cname = need(c, "이름", where)
        where = f"작물 '{cname}'"
        s, e = month_num(c.get("판매시작"), where), month_num(c.get("판매끝"), where)
        months = [(s - 1 + k) % 12 + 1 for k in range((e - s) % 12 + 1)]
        when = f"{s}월 – {e}월" if s <= e else f"{s}월 – 이듬해 {e}월"
        if s == e:
            when = f"{s}월"
        check_photo(need(c, "사진", where), where)
        crops.append({"name": cname, "season": months, "when": when,
                      "photo": c.get("사진"), "desc": fill(need(c, "설명", where))})
    if not crops:
        problems.append("'작물' 목록이 비어 있습니다.")

    hero = d.get("첫화면") or {}
    for i, p in enumerate(hero.get("사진") or [], 1):
        check_photo(p.get("파일"), f"첫화면 사진 {i}번째")
    about = d.get("농원소개") or {}
    check_photo(about.get("사진"), "농원소개")
    diary = d.get("농장일기") or []
    for p in diary:
        check_photo(p.get("사진"), f"농장일기 '{p.get('제목')}'")

    schedule = ", ".join(f"{c['name']} {c['when']}" for c in crops)
    faq = []
    for q in d.get("자주묻는질문") or []:
        a = str(q.get("답", "")).strip()
        if a == "자동":
            a = f"{schedule}입니다. 그해 날씨와 수확량에 따라 조금씩 달라질 수 있습니다."
        faq.append({"q": fill(q.get("질문")), "a": fill(a)})

    if problems:
        sys.exit("\n[오류] 농원정보.yml을 확인해 주세요:\n - " + "\n - ".join(problems) + "\n")

    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    cur = now.month
    on_sale = [c for c in crops if cur in c["season"]]
    nxt = ""
    for k in range(1, 13):
        mm = (cur - 1 + k) % 12 + 1
        starting = [c["name"] for c in crops if c["season"][0] == mm and cur not in c["season"]]
        if starting:
            nxt = f"{mm}월 " + ", ".join(starting)
            break

    calendar = [{"name": sn, "range": f"{ms[0]} – {ms[-1]}월",
                 "months": [{"m": m, "crops": [c["name"] for c in crops if m in c["season"]]} for m in ms]}
                for sn, ms in SEASONS]

    crop_names = [c["name"] for c in crops]
    keywords = ["강화 농산물", "강화도 농산물"] + [f"강화 {n}" for n in crop_names] + \
               ["강화 직거래", "강화 농원"] + [w for w in str(addr).split() if w.endswith(("면", "리"))] + [name]
    top3 = "·".join(str(x) for x in (d.get("대표작물") or crop_names[:3]))

    ld_business = {
        "@context": "https://schema.org", "@type": "LocalBusiness",
        "name": name, "alternateName": f"강화 {name}", "url": url,
        "description": f"{addr}에서 {', '.join(crop_names)} 등을 직접 재배해 농원 방문 판매와 택배로 판매하는 가족 농원. 대량 주문·납품 상담 가능.",
        "telephone": tel,
        "address": {"@type": "PostalAddress", "streetAddress": " ".join(str(addr).split()[2:]),
                    "addressLocality": str(addr).split()[1] if len(str(addr).split()) > 1 else "",
                    "addressRegion": str(addr).split()[0], "addressCountry": "KR"},
        "areaServed": "대한민국",
        "image": url + "images/" + ((hero.get("사진") or [{}])[0].get("파일") or ""),
        "knowsAbout": [f"강화 {n}" for n in crop_names],
        "makesOffer": [{"@type": "Offer", "itemOffered": {"@type": "Product", "name": f"강화 {c['name']}"},
                        "description": f"판매 시기 {c['when']}. {c['desc']}"} for c in crops],
    }
    if d.get("블로그주소"):
        ld_business["sameAs"] = [d["블로그주소"]]
    ld_faq = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": f["q"],
                              "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}

    credits = []
    for line in d.get("사진출처") or []:
        text, _, link = str(line).partition("|")
        credits.append({"text": text.strip(), "link": link.strip()})

    ctx = dict(
        name=name, url=url, addr=addr, tel=tel, tel_digits=tel_digits,
        logo_sub=d.get("작은로고글자", ""),
        naver=str(d.get("네이버인증코드") or "").strip(), google=str(d.get("구글인증코드") or "").strip(),
        blog=str(d.get("블로그주소") or "").strip(),
        hero=hero, hero_title=lines(hero.get("제목")),
        about=about, about_title=lines(about.get("제목")),
        crops=crops, on_sale=on_sale, cur=cur, nxt=nxt, calendar=calendar,
        empty_month=d.get("판매없는달문구", ""), empty_now=lines(d.get("판매없는달안내")),
        ways=d.get("구매방법") or [], order_note=fill(d.get("주문안내")), bulk_note=fill(d.get("대량문의")),
        diary=diary, faq=faq, credits=credits,
        keywords=", ".join(dict.fromkeys(keywords)), top3=top3,
        crops_js=json.dumps([{"name": c["name"], "season": c["season"], "when": c["when"],
                              "photo": c["photo"], "desc": c["desc"]} for c in crops], ensure_ascii=False),
        ld_business=json.dumps(ld_business, ensure_ascii=False),
        ld_faq=json.dumps(ld_faq, ensure_ascii=False),
        today=now.strftime("%Y-%m-%d"), year=now.year,
        ways_text=", ".join(w.get("제목", "") for w in d.get("구매방법") or []),
    )

    env = Environment(loader=FileSystemLoader(ROOT / "template"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(IMG, OUT / "images")
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
    print(f"완료: 작물 {len(crops)}개, 이달({cur}월) 판매 {len(on_sale)}개 → _site/")


if __name__ == "__main__":
    main()
