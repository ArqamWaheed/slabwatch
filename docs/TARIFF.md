# Pakistan domestic electricity tariff, as of 24 Oct 2026 (for Slabwatch)

Legend: **[V]** read in the primary document (NEPRA/MoE PDF, downloaded and text/OCR-extracted 2026-10-24) · **[S]** reputable secondary only · **[U]** unverified / inferred.

nepra.org.pk served all PDFs to `curl` with a browser User-Agent. Several are scanned images, so I read them with OCR (tesseract). Wherever OCR and the clean K-Electric Annex-C text disagree, I note it.

---

## 0. Headline correction: there is no "FY2026-27 July rebasing"

- **[V]** Rebasing moved from a fiscal-year cycle (1 July) to a **calendar-year cycle (1 January)**. The Power Division (MoE-PD) asked for this in a letter dated 18.08.2025, to avoid summer FCA and rebasing shocks landing together. NEPRA accepted the shift in its LESCO revised-rebasing determination dated **07 Jan 2026** ([PDF](https://nepra.org.pk/tariff/Tariff/Ex-WAPDA%20DISCOS/2026/TRF-603%20&TRF%20604%20LESCO%20FOR%20DETERMINATION%20OF%20TARIFF%20REVISED%20ANNUAL%20REBASING%2007-01-2026%20237-44.PDF)).
- **[V]** CY2026 uniform tariff: NEPRA decision on the Federal Government motion dated **12 Jan 2026**, effective **01.01.2026**. MoE notified it through SROs 41(I)–52(I)/2026 dated 13.01.2026 ([decision PDF](https://nepra.org.pk/tariff/Tariff/Ex-WAPDA%20DISCOS/2026/Decision%20of%20the%20Authority%20Motion%20of%20Federal%20Govt.%201004-23%20dated%2012.01.2026.PDF)). Domestic variable rates did not change from FY2025-26 ("no change in base tariff of any consumer category / slab").
- **[V] The tariff in force now is the "Rationalization of Tariff" revision.** NEPRA decision dated **11 Feb 2026** ([PDF](https://nepra.org.pk/tariff/Tariff/Ex-WAPDA%20DISCOS/2026/TRF-100%20XWDISCOS%20AND%20KE%20RATIONALIZATION%20OF%20TARIFF%2011-02-2026%202935-57.pdf)), notified by MoE as **S.R.O. 279(I)/2026 dated 12 Feb 2026**, "notify immediately", modifying SROs 41–52/2026 ([SRO PDF](https://nepra.org.pk/tariff/Tariff/Notifications/2026/02%20Feb/S.R.O.%20279(1)2026%20dated%2012-02-2026.pdf)). The cabinet approved it in Case No.89/Rule-19/2026/111 on 04.02.2026. It **added per-kW fixed charges for every domestic consumer except lifeline** and cut variable rates for slabs above 300 units.
- **[S]** Next rebasing is for CY2027. The CPPA-G PPP forecast for CY2027 is posted on NEPRA's Oct 2026 admission notices, with a hearing reported for 3 Nov 2026 ([Minute Mirror](https://minutemirror.com.pk/pakistan-begins-process-to-set-new-electricity-base-tariff-for-2027-647721/)). **[U]** New slabs would probably take effect around 1 Jan 2027, so Slabwatch's tariff table must be easy to swap.
- Ignore aggregator blogs (toolsfluent, bijlibills, ebillpakistan, checkyourbill). Several still show pre-Feb-2026 or illustrative numbers.

## 1. Domestic A-1 tariff (ex-WAPDA DISCOs and K-Electric, uniform), in force since 12 Feb 2026

Source: **[V]** the "GoP Applicable" columns of Annex-A-1 (XWDISCOs, OCR) and Annex-C (KE, clean text) of the 11 Feb 2026 decision, cross-checked against the MoE motion table in the same PDF. The rates are uniform across LESCO, IESCO, FESCO, GEPCO, MEPCO, PESCO, HESCO, SEPCO, QESCO, TESCO, HAZECO and KE.

Applies to non-ToU A-1(a) connections with sanctioned load below 5 kW.

```yaml
# Slabwatch tariff table — effective 2026-02-12 (SRO 279(I)/2026). Rs.
lifeline:          # single-phase, sanctioned load <=1 kW, max(last 12 months + current) <=100 kWh
  - {from: 1,  to: 50,  rate: 3.95, fixed_per_kw: 0}
  - {from: 51, to: 100, rate: 7.74, fixed_per_kw: 0}
  slab_benefit: none          # all units billed at the single applicable rate
protected:         # non-ToU residential, <=200 kWh in EACH of the past 6 months
  - {from: 1,   to: 100, rate: 10.54, fixed_per_kw: 200}
  - {from: 101, to: 200, rate: 13.01, fixed_per_kw: 300}
  slab_benefit: one_previous_slab   # 150 units = 100*10.54 + 50*13.01
unprotected:
  - {from: 1,   to: 100,  rate: 22.44, fixed_per_kw: 275}
  - {from: 101, to: 200,  rate: 28.91, fixed_per_kw: 300}
  - {from: 201, to: 300,  rate: 33.10, fixed_per_kw: 350}
  - {from: 301, to: 400,  rate: 36.46, fixed_per_kw: 400}
  - {from: 401, to: 500,  rate: 38.95, fixed_per_kw: 500}
  - {from: 501, to: 600,  rate: 40.22, fixed_per_kw: 675}
  - {from: 601, to: 700,  rate: 41.85, fixed_per_kw: 675}
  - {from: 701, to: null, rate: 47.20, fixed_per_kw: 675}
  slab_benefit: none          # whole month's units at the slab's rate (see note)
tou_5kw_plus: {peak: 46.85, offpeak: 34.53, fixed_per_kw: 675}  # on max(50% sanctioned load, MDI)
fixed_charge_basis_non_tou: sanctioned_load_kw
min_monthly_charge: {single_phase: 75, three_phase: 150}  # only where no fixed charge applies (i.e. lifeline)
```

Notes:
- **[V]** Schedule notes, verbatim in substance: "only protected residential consumers will be given the benefit of one previous slab"; "residential life line consumer will not be given any slab benefit"; "fixed charges for Non-ToU domestic consumers shall be applicable based on the sanctioned load".
- **[V→inference]** Unprotected billing is **not telescopic**. Because unprotected users get no slab benefit, all units in the month are billed at the rate of the slab the total falls in: 210 units = 210 × 33.10. Pakistan Observer reports the same reading ([21 Sep 2026](https://pakobserver.net/?p=777578)). Expect a sharp jump at 300/301 too: 300 × 33.10 = 9,930, but 301 × 36.46 = 10,974.
- **[U]** The document does not say which fixed-charge row applies to a given month. I assume it is the row of that month's consumption slab, multiplied by sanctioned kW. I have not seen this on a real bill.
- **[V/OCR]** Minimum-charge figures: OCR read the single-phase amount as "76" in one pass and "70" in another, while older schedules say Rs.75. The three-phase figure is clearly Rs.150. **Treat 75 as [U]**.
- What changed on 12 Feb 2026 (old → new, all **[V]**): 301-400 went from Rs37.99 plus Rs200 per consumer to Rs36.46 plus Rs400/kW. 401-500 went from Rs40.20 plus Rs400 per consumer to Rs38.95 plus Rs500/kW. 501-600 was Rs41.62, 601-700 was Rs42.76 and above-700 was Rs47.69, each with Rs600/800/1,000 per consumer before; they now carry Rs675/kW. Slabs at 300 units and below kept their variable rates and gained a per-kW fixed charge.

## 2. The protected-consumer rule

- **[V] Definition:** "Protected consumers" are "Non-ToU residential consumers consuming ≤200 kWh per month consistently for the past 6 months" (LESCO determination of 07 Jan 2026, Part-II A-1 definitions). Lifeline consumers are single-phase connections with sanctioned load up to 1 kW whose maximum consumption over the last 12 months plus the current month is ≤100 units.
- **[S] Effect of one breach:** a single month above 200 units removes protected status. The household then needs 6 consecutive months at ≤200 to regain it, so in practice it pays unprotected rates for at least the next 6 bills even if usage falls back. Sources: [Daily Pakistan, 3 Aug 2026](https://en.dailypakistan.com.pk/03-Aug-2026/protected-vs-non-protected-electricity-rates-in-pakistan-for-200-units-2026-update), [Pakistan Observer, 21 Sep 2026](https://pakobserver.net/?p=777578), and the K-Electric statement in [Minute Mirror](https://minutemirror.com.pk/viral-200-units-claim-declared-misleading-593153/) that protected status can be regained after 6 consecutive months ≤200.
- **[S] 2026 proposals, none notified as of 24 Oct 2026:**
  - Power Division is reviewing a "penalty only in the month of excess" change (reported around 21 Sep 2026 by [Samaa](https://www.samaa.tv/2087357132-govt-considers-relief-for-consumers-crossing-200-electricity-units), [Dunya](https://dunyanews.tv/en/Business/973950-power-division-considers-relief-for-nonprotected-domestic-electricity), [TechJuice](https://www.techjuice.pk/power-division-may-end-six-month-penalty-for-crossing-200-units/) and Pakistan Observer). It reportedly needs IMF sign-off.
  - Raising the 200-unit limit to 300 has been floated but not announced (Daily Pakistan, Aug 2026).
  - Replacing the protected category with a BISP-targeted subsidy is an IMF commitment, reportedly due by **end-Jan 2027** ([Arab News](https://www.arabnews.pk/pakistan/pakistan-weighs-subsidy-overhaul-as-imf-pushes-for-targeted-relief-3002884), [Geo](https://www.geo.tv/latest/615235-govt-plans-phase-out-of-protected-power-consumers)).
- **[V, absence]** NEPRA's 2026 notification list (checked 24 Oct 2026) shows no SRO changing the protected definition. **Slabwatch should treat the 6-month rule as current and expect a change at the CY2027 rebasing.**

## 3. Adjustments, surcharges, taxes

| Item | Value / rule | Who pays | Status |
|---|---|---|---|
| **FCA (monthly)** | Recovered 2 months after the consumption month. Billed on the units billed in the reference month and shown as a separate line. | All categories **except lifeline, EV charging stations and prepaid**. **Protected consumers are NOT excluded** in the decision text. | [V] |
| Jul 2026 FCA | **+Rs2.0581/kWh** (CPPA-G asked 2.5182), on Sep 2026 bills. Decision 04 Sep 2026, SRO 1499(I)/2026. [PDF](https://nepra.org.pk/tariff/Tariff/Ex-WAPDA%20DISCOS/2026/TRF-100%20MFPA%20FOR%20THE%20MONTH%20OF%20JULY%202026%20EX-WAPDA%20DISCOS%2004-09-2026%2018342-60.PDF) | same | [V] |
| Aug 2026 FCA | **+Rs1.1086/kWh**: actual Rs8.2084 vs reference Rs7.0998, CPPA-G asked 1.7267. On **Oct 2026** bills. Decision 07 Oct 2026. [PDF](https://nepra.org.pk/tariff/Tariff/Ex-WAPDA%20DISCOS/2026/D-20276-94%20Decision%20FCA%20for%20XW-DISCOs%20August%202026%2007.10.2026.PDF). Tribune [8 Oct 2026](https://tribune.com.pk/story/2633704/nepra-allows-rs111-per-unit-fuel-adjustment-in-october-billing) | same, KE included | [V] |
| **Sep 2026 FCA** | **Requested +Rs2.5624/kWh**: actual Rs10.0220 vs reference Rs7.4596. CPPA-G letter dated 15 Oct 2026 ([PDF](https://nepra.org.pk/Admission%20Notices/2026/10%20Oct/FCA_Sep-26_Sent%20to%20NEPRA_15-Oct-2026.pdf)). **Hearing 29 Oct 2026** ([notice](https://nepra.org.pk/Admission%20Notices/2026/10%20Oct/FPA%20XWDISCOs.jpeg)), to apply to KE too. Expected on Nov 2026 bills ([Tribune](https://tribune.com.pk/story/2635319/discos-seek-rs26unit-hike-for-sept), Minute Mirror). NEPRA has approved less than requested every month checked in 2026. | — | request [V], decision pending |
| **QTA (quarterly)** | Q2 CY2026: **+Rs0.5194/kWh** on **Sep, Oct and Nov 2026** bills. SRO 1501(I)/2026 dated 07 Sep 2026 ([PDF](https://nepra.org.pk/tariff/Tariff/Notifications/2026/09%20Sep/SRO%201501(I)-2026%20Dated%2007-09-2026.pdf)). The previous quarter (Q1 CY2026) was **−Rs1.9857/kWh** on Jun–Aug 2026 bills (SRO 953(I)/2026, 08 Jun 2026). | All **except lifeline**, incremental-package units and prepaid. KE included. | [V] |
| Q3 CY2026 QTA (Jul–Sep) | Not yet filed or decided. By pattern, probably on Dec 2026–Feb 2027 bills. | — | [U] |
| **Debt Service Surcharge** (shown on bills as "FC surcharge" [U]) | Rs3.23/kWh. Protected consumers (≤200) and agricultural tubewells pay **Rs0.43/kWh**. In force since 1 Jul 2023, retained up to 6 years. Sources: [Dawn 1 Apr 2023](https://www.dawn.com/news/amp/1745294), [BR](https://www.brecorder.com/news/amp/40234833), [Profit 15 Jan 2026](https://profit.pakistantoday.com.pk/2026/01/15/rs3-23-per-unit-electricity-debt-surcharge-to-remain-for-up-to-six-years/). The NEPRA 12 Jan 2026 decision quotes a commentator saying consumers pay "DSS of Rs 3.23/kWh" [V that it is referenced]. | Non-protected: 3.23. Protected: 0.43. Lifeline: [U] | [S] |
| **GST** | 18% of energy + fixed + FCA + QTA + surcharges | All domestic. Any low-use exemption [U] (a 2012 BR report says only 1-50 unit lifeline users were exempt). | [S]/[U] |
| **Electricity duty** | Federal government stopped collecting it through bills from **1 Jul 2025** (Energy Minister letter to the CMs, [Profit 1 Jul 2025](https://profit.pakistantoday.com.pk/2025/07/01/govt-abolishes-electricity-duty-on-bills-offers-relief-to-consumers)). Punjab's Electricity Duty Rules 2026 exempt domestic users ([Daily Times, Jun 2026](https://dailytimes.com.pk/1501187/punjab-okays-electricity-duty-rules-2026/)). | — | [S] |
| **PTV fee** (Rs35) | Removed from bills, announced 29 Jun 2025 ([Profit](https://profit.pakistantoday.com.pk/2025/08/27/government-approves-rs11-billion-subsidy-for-ptv-after-tv-fee-withdrawal/)). | — | [S] |
| **Income tax (s.235)** | Domestic: 7.5% for non-ATL consumers whose monthly bill is ≥Rs25,000. Active-taxpayer-list (ATL) filers are exempt. | Big bills only | [U]: rate and threshold from blogs only. Not needed below about 600 units. |
| NJ surcharge (Rs0.10/kWh), Tariff Rationalization Surcharge, extra/further tax | Not checked for 2026 | — | [U] |

## 4. K-Electric (Karachi)

- **[V]** KE consumers pay the same GoP-applicable uniform A-1 rates and fixed charges (Annex-C of the 11 Feb 2026 decision; KE confirmed the 12 Feb 2026 revision on [X](https://x.com/KElectricPk/status/2033831175848952170)). The government covers the gap through subsidy against KE's own multi-year tariff (MYT; base Rs32.37 per [Dawn](https://www.dawn.com/news/2032223/nepra-notifies-ke-base-tariff-at-rs3237-per-unit)).
- **[V]** Since 2026 the monthly FCA and the quarterly QTA are also **uniform**: the XWDISCO figure applies to KE "with same applicability period". KE no longer has a separate FCA stream.
- **[S]** Billing-cycle dates, bill layout, and any Sindh-specific duty or levies differ. Not researched.

## 5. Worked example: October 2026 bill (ESTIMATE, not a bill)

Assumptions **[U]**: LESCO, single-phase, **sanctioned load 2 kW**, filer. Fixed charge = that month's slab row × kW. GST at 18% on all listed components. DSS as in §3. No electricity duty, PTV fee or income tax. October bills carry the Aug FCA (1.1086) and the Q2 QTA (0.5194).

| Component | A: 180 u, protected | B: 210 u, unprotected | C: 180 u, protection lost (breach within last 6 months) |
|---|---|---|---|
| Energy | 100×10.54 + 80×13.01 = **2,094.80** | 210×33.10 = **6,951.00** | 180×28.91 = **5,203.80** |
| Fixed (Rs/kW × 2) | 300×2 = 600.00 | 350×2 = 700.00 | 300×2 = 600.00 |
| FCA Aug-26 @1.1086 | 199.55 | 232.81 | 199.55 |
| QTA @0.5194 | 93.49 | 109.07 | 93.49 |
| DSS / "FC surcharge" | 0.43×180 = 77.40 | 3.23×210 = 678.30 | 3.23×180 = 581.40 |
| Subtotal | 3,065.24 | 8,671.18 | 6,678.24 |
| GST 18% | 551.74 | 1,560.81 | 1,202.08 |
| **Estimated total** | **≈ Rs3,617** | **≈ Rs10,232** | **≈ Rs7,880** |

Going from 180 to 210 units (+17%) roughly **2.8×** the bill. Case C shows the "hangover": once protection is lost, the same 180 units cost about 2.2× more for the following months. That is the alert Slabwatch should sell. For November, swap the FCA for the Sep-26 decision (requested 2.5624, final unknown). The QTA stays at 0.5194.

## 6. Uncertain or unverified, to check before shipping

1. Whether the fixed-charge row follows that month's slab, and that the multiplier is sanctioned kW rounded as-is. Check against a real post-Feb-2026 LESCO bill.
2. The DSS amount per category in 2026 (0.43 vs 3.23), and whether lifeline pays any. I have only 2023 secondary reports.
3. GST base and any low-consumption exemption. The s.235 income-tax rate and threshold.
4. Exact 6-month mechanics: rolling window versus the bill month, and whether the current month counts. The definition says "past 6 months". The proposal to limit the penalty to one month is unresolved, as is the possible end of the protected category around Jan 2027 under the BISP plan.
5. Single-phase minimum charge: Rs75 or a different figure (OCR ambiguity). It only matters for lifeline.
6. Sep-26 FCA final value (hearing 29 Oct 2026). Q3 CY2026 QTA value and timing.
7. Whether DISCOs bill FCA to protected consumers in practice. The NEPRA order excludes only lifeline, but past governments have sometimes absorbed it.
8. Any Punjab or other provincial relief packages layered on top (not checked).
