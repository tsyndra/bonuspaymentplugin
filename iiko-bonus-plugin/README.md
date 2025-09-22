# iiko Bonus External Payment Plugin (Skeleton)

Minimal skeleton of an iikoFront external payment plugin to redeem bonuses from your external loyalty API.

What’s included:
- Class Library (.NET Framework 4.7.2) with WPF
- Plugin class skeleton (Init/Dispose)
- External payment processor factory + processor (placeholders for SDK interfaces)
- Simple WPF dialog (phone/balance/redeem amount)
- HTTP client for loyalty API (reserve/commit/cancel)
- App.config with ApiBaseUrl, ApiKey, PaymentTypeName

Requirements:
- Windows + Visual Studio 2019/2022
- iikoFront installed (to get Resto.Front.Api.V6.dll)

Setup:
1) Copy `Resto.Front.Api.V6.dll` from your iikoFront installation to `BonusPaymentPlugin/lib/` or update `HintPath` in `BonusPaymentPlugin.csproj` to your installation path.
2) Open `BonusPaymentPlugin/BonusPaymentPlugin.csproj` in Visual Studio.
3) Update `App.config` with your API URL and key. Ensure `PaymentTypeName` equals your External Payment Type in iikoOffice (e.g. "Бонусы").
4) Replace TODOs in code with exact SDK interfaces if your version differs, then build.
5) Build in Release. Output: `BonusPaymentPlugin.dll` and `BonusPaymentPlugin.dll.config`.

Deploy:
- Create folder: `C:\Program Files\iiko\iikoRMS\Front.Net\Plugins\BonusPaymentPlugin`
- Copy `BonusPaymentPlugin.dll`, `BonusPaymentPlugin.dll.config`, and any dependent files (e.g., `Resto.Front.Api.V6.dll` if needed).
- Restart iikoFront. Test payment type "Бонусы".

Notes:
- Processor factory registration and interface names may vary slightly by SDK version. See iikoFront API docs for your version (v6 commonly used).
- All loyalty operations are idempotent by `reservationId`. Ensure consistent handling for retry/cancel/commit.
