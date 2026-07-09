# AI Frontend Builder — Deep Agent

یک **Deep Agent** که با گرفتن یک ایده‌ی محصول (به فارسی)، به‌صورت خودکار تحلیل نیاز،
سیستم طراحی، برندینگ، مشخصات کامپوننت، انیمیشن، کد Next.js/TypeScript/Tailwind (RTL و
فارسی) و بازبینی کد را تولید می‌کند 
##
معماری

پایپ‌لاین با **LangGraph** پیاده‌سازی شده: هشت Agent + چهار Skill، هر کدام مسئولیت مشخصی دارند
و توسط یک Coordinator هماهنگ می‌شوند.

```
Product Analysis → Design System → Color & Branding → [Figma Export skill]
  → UI Components → Animation → Frontend Developer → [SEO skill, Hero Images skill]
  → Code Review → [Accessibility skill] → (bounded fix loop) → Coordinator (finalize)
```

قابلیت‌های Deep Agent:

| قابلیت | پیاده‌سازی |
|---|---|
| **Planning** | [deepagent/planning.py](deepagent/planning.py) — Todo Plan در `plan.json`، قبل از اجرا ساخته و حین اجرا به‌روزرسانی می‌شود. |
| **Memory** | [deepagent/memory.py](deepagent/memory.py) — `MemoryStore` تصمیمات هر Agent را در `memory/decisions.json` نگه می‌دارد؛ بین اجراها (resume) پایدار است. |
| **Context Management** | `summarize_for_context()` در همان فایل — آرتیفکت کامل همیشه روی دیسک ذخیره می‌شود؛ فقط خلاصه‌اش به مرحله بعد پاس داده می‌شود. |
| **Filesystem** | [deepagent/workspace.py](deepagent/workspace.py) — تنها نقطه‌ی I/O برای همه Agent ها و Skill ها. |
| **Skill System** | [deepagent/skills/base.py](deepagent/skills/base.py) — افزودن Skill جدید فقط با اضافه‌کردن یک فایل به `deepagent/skills/`. |
| **Sub Agent Support** | [deepagent/graph.py](deepagent/graph.py) — گراف LangGraph با یک Node به‌ازای هر Agent. |

### Agent ها

1. **Coordinator** — [agents/coordinator.py](deepagent/agents/coordinator.py)
2. **Product Analysis** — [agents/product_analysis.py](deepagent/agents/product_analysis.py)
3. **Design System** — [agents/design_system.py](deepagent/agents/design_system.py)
4. **Color & Branding** — [agents/color_branding.py](deepagent/agents/color_branding.py) (شامل Theme Generator روشن/تاریک)
5. **UI Components** — [agents/ui_components.py](deepagent/agents/ui_components.py) (پایه‌ی Component Library)
6. **Animation** — [agents/animation.py](deepagent/agents/animation.py)
7. **Frontend Developer** — [agents/frontend_developer.py](deepagent/agents/frontend_developer.py) (Next.js واقعی + Multi Page Support)
8. **Code Review** — [agents/code_review.py](deepagent/agents/code_review.py) (+ چرخه رفع اشکال محدود)

### Skill ها

- `figma_export_skill` — خروجی Design Tokens (فرمت DTCG) + Wireframe SVG برای import در Figma.
- `seo_skill` — تولید `sitemap.ts` / `robots.ts`.
- `hero_images_skill` — دانلود یک عکس واقعی و مرتبط با موضوع سایت از Unsplash برای بخش Hero
  هر صفحه (به‌همراه رعایت الزام Unsplash API: نمایش credit عکاس + ping مربوط به download).
  نیازمند `UNSPLASH_ACCESS_KEY` در `.env`؛ در غیر این صورت این مرحله بی‌خطر رد می‌شود.
- `accessibility_skill` — بررسی heuristics دسترس‌پذیری (alt text، aria-label).

> **نکته درباره Figma Export:** push زنده به Figma فقط از طریق MCP تعاملی Claude Code (با
> Figma Desktop باز) ممکن است؛ این برنامه‌ی مستقل Python از آن استفاده نمی‌کند. به‌جایش
> خروجی استاندارد (DTCG JSON + SVG) تولید می‌شود که مستقیماً در Figma قابل import/paste است.

## نصب و اجرا

پیش‌نیاز: Python 3.11+، Node.js 18+، و مقادیر `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`
در فایل `.env` (یک پروکسی سازگار با OpenAI API). به‌صورت اختیاری `UNSPLASH_ACCESS_KEY`
(از https://unsplash.com/developers) برای فعال شدن Skill عکس Hero.

```bash
pip install -r requirements.txt
python -m deepagent
```

سپس ایده‌ی خود را به فارسی وارد کن، مثلاً:

```
> یک فروشگاه آنلاین کفش بساز
```

پس از پایان اجرا، خروجی در `workspace/<slug>/` قرار می‌گیرد:

```
workspace/<slug>/
  plan.json                    # Todo Plan
  memory/decisions.json        # Memory
  spec/product-analysis.md
  design/
    design-tokens.json
    design-tokens.figma.json   # Figma Export (DTCG)
    wireframes/*.svg           # Figma Export (wireframe)
    design-system.md, branding.md, components-spec.md, animations.md, seo.md
  review/code-review.md
  README.md                    # خلاصه نهایی پروژه
  site/                        # پروژه واقعی Next.js
```

برای اجرای سایت تولیدشده:

```bash
cd workspace/<slug>/site
npm install
npm run dev
```

### دستورات داخل CLI

- `/plan` — نمایش Todo Plan فعلی
- `/memory` — نمایش تصمیمات ثبت‌شده در Memory
- `/skills` — لیست Skill های موجود
- `/resume <slug>` — بارگذاری یک پروژه‌ قبلی از `workspace/`
- `/exit` — خروج

## افزودن یک Skill جدید
یک فایل در `deepagent/skills/` بساز که از `Skill` (در `deepagent/skills/base.py`) استفاده 
می‌کند، `stage` را روی یکی از مراحل `deepagent/planning.py` تنظیم کن، منطق را در `run()`
بنویس و در انتهای فایل `register(YourSkill())` را صدا بزن. نیازی به تغییر بقیه معماری نیست.
