# مابات عبودين — Roblox

نشر ملفات المابات إلى تجارب Roblox الموجودة عبر GitHub Actions.

## الماب الحالي

`maps/Boulevard-Jood.rbxlx.gz` نسخة مضغوطة دون فقدان من الملف المرفق **Boulevard-Jood(1).rbxlx**. يفك الناشر الضغط ويُرسل نفس البايتات الأصلية دون تغيير المحتوى أو التصميم. يمكنك فك الضغط لفتحه في Studio. حجمه **13,479,692 بايت**. بصمته محفوظة في `maps/SHA256SUMS`.

رفع الملفات إلى GitHub يشغّل الفحص فقط. **النشر إلى Roblox يدوي** ويتطلب تحديد التجربة والمكان.

## النشر من الجوال

1. افتح [Publish to Roblox](https://github.com/3wasfnjd/Roblex/actions/workflows/publish-roblox.yml).
2. اضغط **Run workflow** واختر فرع `main`.
3. اترك `map_file` كما هو لماب جود، وأدخل **Universe ID** و**Place ID** الخاصين به.
4. اضغط **Run workflow**. عند النجاح يظهر رقم النسخة المنشورة ورابط الماب في ملخص التشغيل.

يُنشئ هذا الإجراء نسخة منشورة جديدة للمكان المحدد ويستبدل محتواه بالملف المختار. لا يغير إعدادات الجمهور أو التصنيف العمري. وجود الملف في المستودع أو نجاح الفحص وحده لا يعني نشره إلى Roblox.

## الإعدادات

- اسم السر في GitHub: **`ROBLOX_API_KEY`**.
- اسم المفتاح في لوحة Roblox: **`aboden`**؛ هذا الاسم لا يغيّر اسم السر في GitHub.
- يحتاج المفتاح صلاحية **`universe-places` → `Write`** للتجربة المستهدفة، مع صلاحية زمنية ونطاقات IP تسمح بتشغيل GitHub Actions.
- لا تضع قيمة المفتاح في الملفات أو مدخلات تشغيل الـ workflow.

من [لوحة Roblox](https://create.roblox.com/dashboard/creations): افتح قائمة ⋯ للتجربة وانسخ **Universe ID**. ثم افتح التجربة → **Places** → المكان؛ رقم المكان موجود في الرابط:

`https://create.roblox.com/dashboard/creations/experiences/UNIVERSE_ID/places/PLACE_ID/configure`

## استخدام المستودع لماب آخر

أضف ملف `.rbxlx` أو `.rbxl` (أو نسخته المضغوطة بصيغة `.gz`) إلى `maps/`، ثم اختر مساره وأرقام وجهته عند تشغيل النشر. لا توجد أرقام تجربة ثابتة داخل الكود. يجب أن يكون مفتاح Roblox مخولًا للتجربة الجديدة أيضًا.

عند تحديث ماب جود، حدّث بصمته معه:

```sh
sha256sum maps/Boulevard-Jood.rbxlx.gz > maps/SHA256SUMS
```

## الفحص والحدود

```sh
python3 -m unittest discover -s tests -v
sha256sum --check maps/SHA256SUMS
python3 scripts/roblox_publish.py validate maps/Boulevard-Jood.rbxlx.gz
```

يفحص XML وحجم الملف وبصمته وأنواع العناصر المحفوظة غير المدعومة في Open Cloud. ملفات `.rbxl` الثنائية يُفحص رأسها وحجمها فقط؛ راجع أنواع عناصرها داخل Studio. الفحص لا يشغّل اللعبة أو يختبر أداءها. أخطاء الشبكة لا تُعاد تلقائيًا لتجنب نشر نسخة مكررة؛ افحص لوحة Roblox قبل إعادة المحاولة.

مرجع Roblox: [دليل نشر الأماكن عبر Open Cloud](https://create.roblox.com/docs/cloud/guides/usage-place-publishing).
