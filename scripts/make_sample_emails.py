"""Generate the 20 synthetic test e-mails in resources/sample_emails.

Modelled on the real DCR threads (PQI reports, supplier disputes, cold-chain excursions, recalls,
GDP issues, auto-replies, pure logistics coordination). People and supplier names are fictional.

    python scripts/make_sample_emails.py [output_dir]
"""

from email.utils import format_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "resources" / "sample_emails"
OUT.mkdir(parents=True, exist_ok=True)
CET = timezone(timedelta(hours=2))

AMEX_SIG = {
    "jmarkovic": "Jelena MARKOVIC\nSenior Operations Specialist\nAMEX\nP +43 1 876 76 00 - 190\njelena.markovic@amex-healthcare.com | www.amex-healthcare.com\nHeiligenstädter Straße 31/3, 1190 Vienna - Austria",
    "pweiss": "Mag. pharm. Paul WEISS\nQuality Specialist\nAMEX\nP +43 1 876 76 00 - 211\npaul.weiss@amex-healthcare.com | www.amex-healthcare.com\nHeiligenstädter Straße 31/3, 1190 Vienna - Austria",
    "sotieno": "Samuel OTIENO\nWarehouse & Quality Officer\nAMEX Kenya\nP +254 20 000 0000\nsamuel.otieno@amex-healthcare.com | www.amex-healthcare.com\nNairobi, Kenya",
    "lhofer": "Lena HOFER\nSales Specialist\nAMEX\nP +43 1 876 76 00 - 244\nlena.hofer@amex-healthcare.com | www.amex-healthcare.com\nHeiligenstädter Straße 31/3, 1190 Vienna - Austria",
}
ADDR = {
    "jmarkovic": "Jelena Markovic <jelena.markovic@amex-healthcare.com>",
    "pweiss": "Paul Weiss <paul.weiss@amex-healthcare.com>",
    "sotieno": "Samuel Otieno <samuel.otieno@amex-healthcare.com>",
    "lhofer": "Lena Hofer <lena.hofer@amex-healthcare.com>",
    "quality": "Quality <quality@amex-healthcare.com>",
}


def write(name, *, msg_id, sender, to, subject, when, body, cc=None, reply_to_id=None, refs=(), attachments=()):
    headers = [
        f"From: {sender}",
        f"To: {to}",
        *( [f"Cc: {cc}"] if cc else [] ),
        f"Subject: {subject}",
        f"Date: {format_datetime(when)}",
        f"Message-ID: {msg_id}",
        *( [f"In-Reply-To: {reply_to_id}"] if reply_to_id else [] ),
        *( [f"References: {' '.join(refs)}"] if refs else [] ),
        *( [f"X-Attachments: {', '.join(attachments)}"] if attachments else [] ),
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "Content-Transfer-Encoding: 8bit",
    ]
    if attachments:
        body = body + "\n\n[Attachments: " + ", ".join(attachments) + "]"
    (OUT / name).write_text("\n".join(headers) + "\n\n" + body.strip() + "\n", encoding="utf-8")


def quote(sender, when, to, subject, body):
    return (f"\n\nFrom: {sender}\nSent: {when.strftime('%A, %B %d, %Y %I:%M %p')}\nTo: {to}\n"
            f"Subject: {subject}\n\n{body.strip()}")


def d(month, day, hour=10, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=CET)


# ---------------------------------------------------------------- 1-4: PQI bleach (customer QA → supplier)
t1 = d(8, 3, 21, 40)
b1 = """Dear Paul,

Another packaging and labelling incident was reported by our in-country staff regarding the Thick Bleach 5L (Sodium hypochlorite solution 5%), lot 6128, supplied by AMEX Healthcare GmbH, Austria to Haiti under PO 10031187 (AMEX project 20241189). See attached documents.

Similar documentation and labelling issues were previously discussed in October 2025 for the same product and manufacturer (incident 2025-020). It is unfortunate to see this issue reoccurring.

The certificate of analysis (COA) issued by the manufacturer Mirelle Hygiene Solutions indicates the product's expiry date is 27 November 2026. AMEX's invoice specifies the same. The COA and invoice issued by Chemora Diagnostics Ltd, the UK distributor of this product as per our understanding, indicate another expiry date: 31 January 2027. Both COAs have the same manufacturing date, 27 November 2025.

In addition, the lot number is not printed on the primary bottles, only on the outer carton label.

Please investigate and provide a root cause analysis and CAPA within 30 days. Kindly also confirm which expiry date is valid so that the in-country team can decide on release of the 1,960 bottles currently on hold.

Kind regards,
Anna Petrova, B.Pharm., M.Sc.
QA Specialist
FHI 360 PQC – GHSC-PSM Product Quality
"""
write("01_pqi_bleach_expiry_mismatch.eml", msg_id="<pqi-2026-031@fhi360.example>",
      sender="Anna Petrova <apetrova@fhi360.example>", to=ADDR["pweiss"], cc=ADDR["quality"],
      subject="PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", when=t1, body=b1,
      attachments=["PQI_2026-031_report.pdf", "photos_bottles.zip", "COA_Mirelle_6128.pdf", "COA_Chemora_6128.pdf"])

t2 = d(8, 4, 11, 15)
b2 = """Dear Dr Gray,

I am getting back to you on this procurement as unfortunately we received a new discrepancy claim related to the products sent (AMEX PO 24-03106-02, SOP 10152). I am adding our Quality team as they will follow the case, but I want to make sure you have the full overview.

It is quite critical, as this is a claim over the original claim and we need to provide the response required by the customer.

No. 1 – Bottle
Printed MFG date: 27 11 2025. Expiry is not printed; the legend states +12 months from manufacture, which leads to 27 11 2026.
Lot/batch: not printed on the bottle.

No. 2 – Your documents (invoice 12853, packing list, box label)
Expiry: 31/01/2027.

No. 3 – Manufacturer CoA (Mirelle)
Mfg 27/11/2025, Expiry 27/11/2026.

Could you please explain on what basis the expiry date was changed to 31/01/2027 and send us a corrected CoA? We need your reply by Friday.
""" + "\n" + AMEX_SIG["jmarkovic"] + quote("Anna Petrova <apetrova@fhi360.example>", t1, "Paul Weiss", "PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", b1)
write("02_re_pqi_bleach_to_supplier.eml", msg_id="<amex-20241189-a@amex-healthcare.com>",
      sender=ADDR["jmarkovic"], to="Robert Gray <r.gray@chemora-diagnostics.example>",
      cc=f"{ADDR['pweiss']}, {ADDR['quality']}",
      subject="RE: PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", when=t2, body=b2,
      reply_to_id="<pqi-2026-031@fhi360.example>", refs=["<pqi-2026-031@fhi360.example>"])

t3 = d(8, 4, 11, 16)
write("03_auto_reply_supplier_out_of_office.eml", msg_id="<ooo-4471@chemora-diagnostics.example>",
      sender="Linda Reed <l.reed@chemora-diagnostics.example>", to=ADDR["jmarkovic"],
      subject="Automatic reply: RE: PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", when=t3,
      body="""I am now out of the office - back in at 9.00am Monday 10th August 2026 - my emails are not being monitored.
If your enquiry is an emergency or you need an update on an order please contact Robert Gray - r.gray@chemora-diagnostics.example""")

t4 = d(8, 7, 16, 46)
b4 = """Dear Jelena, dear Paul,

Apologies for the delay, the key person at Mirelle was away until today.

Here is the paperwork trail for batch 6128:
Invoice 12853 – Mfg Nov 2025 – Exp Jan 2027
Packing list – Mfg 27/11/2025 – Exp 31/01/2027
Our CofA – Mfg 27.11.2025 – Exp 31.01.2027
Our box label – Exp 31st Jan 2027

It was agreed with AMEX that as there was no expiry on the bottle we could add a box label showing the expiry date. The labelling was not done before the Christmas holidays and the shipment was organised in January 2026, so we set the expiry to January 2027 to give 12 months from the shipping date. The manufacturer has confirmed by e-mail that thick bleach retains its performance for 14 months from the date of manufacture if stored unopened in suitable conditions.

The lot number is not printed on the bottle; the manufacturing date serves as the batch identifier as only one batch was produced that day.

We will issue a corrected CofA showing Nov 2025 – Nov 2026 if you require it, and in future we will not change expiry dates on our documents without written approval from AMEX.

Best regards
Robert

Dr R. Gray
Chemora Diagnostics Ltd, UK
""" + quote(ADDR["jmarkovic"], t2, "Robert Gray", "RE: PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", b2.split("\n\n")[0])
write("04_re_pqi_bleach_supplier_root_cause.eml", msg_id="<chemora-7788@chemora-diagnostics.example>",
      sender="Robert Gray <r.gray@chemora-diagnostics.example>", to=ADDR["jmarkovic"], cc=ADDR["pweiss"],
      subject="Re: PQI 2026-031 Sodium hypochlorite 5% - GHSC-PSM PO10031187", when=t4, body=b4,
      reply_to_id="<amex-20241189-a@amex-healthcare.com>",
      refs=["<pqi-2026-031@fhi360.example>", "<amex-20241189-a@amex-healthcare.com>"],
      attachments=["Mirelle_statement_shelf_life.pdf"])

# ---------------------------------------------------------------- 5-6: truck temperature excursion (pharma)
t5 = d(8, 12, 9, 5)
b5 = """Dear Paul,

Please be informed that the truck shipment from Belmont Biopharma (Puurs, Belgium) to our Hagenbrunn warehouse arrived yesterday, 11 August 2026, for project 20251792 (UNDP Turkmenistan – Gaucher programme).

The data logger in pallet 2 (taliglucerase alfa 200 U vials, lot BB25-0719, 2–8 °C) recorded a temperature excursion: maximum 13.4 °C, above 8 °C for 6 h 40 min during the transit stop in Liège. The polybox on pallet 1 stayed within range.

The goods are quarantined at the warehouse. Logger report and CMR are attached. The truck was booked by our forwarder NordCargo Logistics; according to the driver the reefer unit was switched off during the overnight stop.

Could you please contact the manufacturer for a stability statement? The customer expects delivery by 30 October.
""" + "\n" + AMEX_SIG["jmarkovic"]
write("05_truck_temperature_excursion.eml", msg_id="<amex-20251792-t1@amex-healthcare.com>",
      sender=ADDR["jmarkovic"], to=ADDR["pweiss"], cc=ADDR["quality"],
      subject="Temperature excursion - truck shipment Belgium - Austria (Belmont Biopharma) - project 20251792",
      when=t5, body=b5, attachments=["DL_report_pallet2.pdf", "CMR_NC-55812.pdf"])

t6 = d(8, 19, 13, 55)
b6 = """Dear Paul,

The product is not approved for use after being stored under any storage conditions other than those described in the Prescribing Information. Belmont Biopharma does not suggest or recommend its use in this manner and cannot guarantee the stability of product stored outside the labelled conditions. Use of such product constitutes off-label use and is at the discretion of the institution.

Kind regards,
Medical Information
Belmont Biopharma NV
""" + quote(ADDR["pweiss"], d(8, 12, 15, 0), "medinfo@belmont-biopharma.example",
            "Temperature excursion - truck shipment Belgium - Austria (Belmont Biopharma) - project 20251792",
            "Dear colleagues, please provide a stability statement for lot BB25-0719 exposed to max 13.4 °C for 6 h 40 min. Kind regards, Paul")
write("06_re_truck_excursion_manufacturer_statement.eml", msg_id="<belmont-mi-2211@belmont-biopharma.example>",
      sender="Medical Information <medinfo@belmont-biopharma.example>", to=ADDR["pweiss"],
      subject="RE: Temperature excursion - truck shipment Belgium - Austria (Belmont Biopharma) - project 20251792",
      when=t6, body=b6, reply_to_id="<amex-20251792-t1@amex-healthcare.com>",
      refs=["<amex-20251792-t1@amex-healthcare.com>"])

# ---------------------------------------------------------------- 7: late delivery complaint (Plan International)
t7 = d(8, 20, 16, 31)
write("07_customer_complaint_late_delivery.eml", msg_id="<plan-benin-0820@plan-international.example>",
      sender="Grace Adjovi <grace.adjovi@plan-international.example>", to=ADDR["lhofer"], cc=ADDR["jmarkovic"],
      subject="Late delivery - ACQUISITION OF MEDICAL EQUIPMENT FOR THE SDA PROJECT - PLAN INTERNATIONAL BENIN",
      when=t7, body="""Dear Lena,

We are writing to formally complain about the late delivery of the medical equipment ordered under our contract for the SDA project in Benin (your reference 20251234).

The contract delivery date DAP Cotonou was 30 June 2026. The shipment only arrived on 18 August 2026, seven weeks late, and without prior notification of the delay. As a result the handover to the health centres had to be postponed and our donor reporting deadline was missed.

We request a formal deviation report explaining the cause of the delay and the measures you will take to prevent this in future orders. Please also confirm whether the delay penalty in clause 12 of the contract (0.5% per week, capped at 5%) will be applied to the final invoice.

Best regards,
Grace Adjovi
Supply Chain Manager
Plan International Benin""")

# ---------------------------------------------------------------- 8: ICRC batch mismatch
t8 = d(8, 25, 14, 2)
write("08_icrc_batch_mismatch_packing_list.eml", msg_id="<icrc-202516020@icrc.example>",
      sender="GVA BSC Procurement Services <gva_procurement@icrc.example>", to=ADDR["jmarkovic"],
      subject="ICRC AME01AT/GVA26/031877 / INV26-01122 [Request 202516020] - batch discrepancy",
      when=t8, body="""Hello Jelena,

Upon receipt of the second partial delivery under order AME01AT/GVA26/031877 (your project 20252275) at our Geneva logistics centre, our receiving team found that 12 cartons of Acetylsalicylic acid 75 mg tablets carry batch GP26-0412, while the packing list and invoice INV26-01122 state batch GP26-0388 for the entire quantity (45,000 packs).

Quantities are correct; only the batch information on the documents does not match the goods. The goods are blocked in our system until corrected documents are received.

Please send an amended packing list and certificate of analysis for batch GP26-0412 as soon as possible.

Thank you,
Marc Fontaine
ICRC Logistics – Receiving

CAUTION: This email originated from outside the ICRC.""")

# ---------------------------------------------------------------- 9-10: WHO eye drops excursion at sea
t9 = d(9, 2, 8, 48)
b9 = """Dear Paul,

Shipment SHP-33135 under WHO PO 203760695 REV 1 (your project 20252675) arrived at our Damascus warehouse on 31 August 2026. The data logger shows the container was exposed to temperatures up to 33 °C for 15 days during transhipment in Mersin (labelled storage: below 25 °C).

Affected products:
* OFLOXACIN 0.3% eye drops, 5 ml – 4,000 units, lot VO-OF2604
* TIMOLOL 0.25% eye drops, 5 ml – 2,500 units, lot VO-TM2511
* Metoprolol tartrate 50 mg tablets – 1,200 packs

We have quarantined the goods. Please provide stability data from the manufacturers so we can decide whether to release the shipment or initiate a claim.

Best regards,
Sophie Laurent
Quality Assurance Officer
World Health Organization – Supply Chain
"""
write("09_who_eye_drops_excursion_at_sea.eml", msg_id="<who-shp33135@who.example>",
      sender="LAURENT, Sophie <laurents@who.example>", to=ADDR["pweiss"], cc="WHO HQ Quality Assurance <hqqa@who.example>",
      subject="[EXT] WHO PO 203760695 REV 1/SHP-33135 - temperature excursion eye drops", when=t9, body=b9,
      attachments=["DL_SHP-33135.pdf"])

t10 = d(9, 23, 9, 10)
b10 = """Dear Paul,

Considering the lack of supporting stability data and the potential risk to patients, I consider it appropriate to dispose of the affected stock rather than release it for use. We will proceed with disposal in accordance with the applicable local procedure and will raise a claim for the value of the goods (EUR 18,450) against AMEX.

Please also share your investigation report and the CAPA to prevent unmonitored transhipment of temperature-sensitive products in future.

Best regards,
Sophie
""" + quote(ADDR["pweiss"], d(9, 22, 16, 29), "LAURENT, Sophie", "RE: [EXT] WHO PO 203760695 REV 1/SHP-33135 - temperature excursion eye drops",
            """Dear Sophie,
For metoprolol the manufacturer confirmed that no stability studies cover 15 days at 33 °C and advises disposal as a precaution. For ofloxacin and timolol, Vistula Ophthalmics informed us that no report is available and a stability assessment would take up to 90 days. The forwarder confirmed the container stood uncovered on the quay in Mersin for 15 days because the feeder vessel was cancelled.
Kind regards,
Paul""") + quote("LAURENT, Sophie <laurents@who.example>", t9, "Paul Weiss", "[EXT] WHO PO 203760695 REV 1/SHP-33135 - temperature excursion eye drops", b9)
write("10_re_who_decision_dispose.eml", msg_id="<who-shp33135-r3@who.example>",
      sender="LAURENT, Sophie <laurents@who.example>", to=ADDR["pweiss"], cc=f"{ADDR['quality']}, WHO HQ Quality Assurance <hqqa@who.example>",
      subject="RE: [EXT] WHO PO 203760695 REV 1/SHP-33135 - temperature excursion eye drops", when=t10, body=b10,
      reply_to_id="<amex-who-33135-r2@amex-healthcare.com>", refs=["<who-shp33135@who.example>", "<amex-who-33135-r2@amex-healthcare.com>"])

# ---------------------------------------------------------------- 11-12: supplier recall + customer acknowledgement
t11 = d(9, 8, 17, 13)
b11 = """Dear Paul,

URGENT FIELD SAFETY NOTICE – REC-0931 – Voluntary Recall

Randall Laboratories Ltd is initiating a voluntary recall of Human Assayed Multi-Sera Control Level 2 (cat. no. HN 1531), lots 1788UN and 1790UN, due to an incorrect target value for ALT in the value sheet supplied with these lots, which may lead to acceptance of out-of-range patient results.

Our records show that lot 1788UN (40 kits) was supplied to AMEX Healthcare GmbH under your PO 2200299355 (project 20250342) for a biochemistry analyser installation.

Please:
1. Identify all end users who received the affected lot.
2. Forward this notice to them and ask them to stop using the product.
3. Return the attached acknowledgement form within 10 working days.

Replacement kits from lot 1802UN will be supplied free of charge.

Kind regards,
Claire Morgan
Vigilance Officer (Regulatory Affairs)
Randall Laboratories Ltd, Antrim, UK
"""
write("11_supplier_recall_fsn_control_sera.eml", msg_id="<randall-rec0931@randall-labs.example>",
      sender="Claire Morgan <claire.morgan@randall-labs.example>", to=ADDR["pweiss"],
      subject="REC-0931 Human Assayed Multi-Sera Control - Field Safety Notice - AMEX Healthcare GmbH",
      when=t11, body=b11, attachments=["FSN_REC-0931.pdf", "Acknowledgement_form.docx"])

t12 = d(9, 14, 16, 34)
write("12_re_recall_customer_acknowledgement.eml", msg_id="<monusco-po2200299355@un.example>",
      sender="Yvonne Kasereka <kasereka@un.example>", to=ADDR["pweiss"],
      subject="RE: REC-0931 Human Assayed Multi-Sera Control - Field Safety Notice - AMEX Healthcare GmbH",
      when=t12, reply_to_id="<amex-rec0931-fw@amex-healthcare.com>",
      refs=["<randall-rec0931@randall-labs.example>", "<amex-rec0931-fw@amex-healthcare.com>"],
      body="""Dear Partner,
Bonjour,

Please note that the field safety notice below, along with the attached PDF, has been received and shared with the end user (MONUSCO Level II hospital laboratory, Goma) for records and necessary action. The laboratory confirmed that 31 of the 40 kits of lot 1788UN are still in stock and have been quarantined; 9 kits were already used.

Signed acknowledgement form attached.

Regards,
Yvonne Kasereka
Supply Officer – MONUSCO
""" + quote(ADDR["pweiss"], d(9, 9, 9, 0), "Yvonne Kasereka", "FW: REC-0931 Human Assayed Multi-Sera Control - Field Safety Notice", b11))

# ---------------------------------------------------------------- 13: GDP internal deviation (customer licence / dry container)
t13 = d(9, 14, 10, 42)
write("13_internal_gdp_deviation_customer_licence.eml", msg_id="<amex-20261234-gdp@amex-healthcare.com>",
      sender=ADDR["pweiss"], to=f"{ADDR['lhofer']}, {ADDR['jmarkovic']}", cc=ADDR["quality"],
      subject="RE: MdM BE/AMEX - RfQ 2026-CD01-066 - shipping 2-8 products in dry container",
      when=t13, body="""Hi all,

I have to raise a deviation on project 20261234 (Médecins du Monde Belgium).

1. On 2 September we shipped 2–8 °C products (insulin glargine, 48 packs) to MdM in a standard dry container without a validated passive box or data logger, because the customer "took over responsibility" for the transport conditions in their order. Under EU GDP chapter 9 the supplying wholesaler remains responsible for maintaining temperature conditions during transport, regardless of what the customer accepts. We have no monitoring data for this shipment.

2. We have not received MdM's licence or authorisation to handle pharmaceuticals. Qualification of new customers is a standard step, and AGES raised the same finding in the last two inspections.

Please do not accept this shipping arrangement for any further orders. For 2–8 products we only have two options: a 2–8 °C truck, or a validated box on a 15–25 °C truck. Lena, could you request the licence from MdM this week?

Kind regards,
Paul
""" + "\n" + AMEX_SIG["pweiss"])

# ---------------------------------------------------------------- 14: Kenya warehouse excursion
t14 = d(9, 16, 7, 55)
write("14_kenya_warehouse_temperature_excursion.eml", msg_id="<amexke-wh-0916@amex-healthcare.com>",
      sender=ADDR["sotieno"], to=ADDR["quality"], cc=ADDR["pweiss"],
      subject="Warehouse temperature excursion - Nairobi WH zone B - 15/16 Sept",
      when=t14, body="""Dear Quality team,

During the night of 15 to 16 September 2026 the temperature mapping probes in zone B of the AMEX Kenya warehouse (ambient pharma, 15–25 °C) recorded up to 28.6 °C for about 6 hours (22:10 – 04:05).

The grid power failed at 21:50; the generator started automatically, but the HVAC unit did not resume cooling after the switch-over. The on-call technician restarted the HVAC at 04:00.

Stock in zone B at the time: oral antibiotics and ORS for the UNHCR project 20252300 (approx. 36 pallets). All pallets have been put on hold in the WMS pending your assessment.

Temperature report attached. We will ask the HVAC supplier to check the automatic restart after power changeover.

Best regards,
""" + AMEX_SIG["sotieno"], attachments=["TempReport_ZoneB_15-16Sep.pdf"])

# ---------------------------------------------------------------- 15: supplier production delay
t15 = d(9, 1, 15, 5)
write("15_supplier_production_delay.eml", msg_id="<galena-delay-0901@galena-pharma.example>",
      sender="Order Desk <orders@galena-pharma.example>", to=ADDR["jmarkovic"],
      subject="Delay in production - Acetylsalicylic acid 75 mg - AMEX PO 25-04418",
      when=t15, body="""Dear Ms Markovic,

We regret to inform you that production of the remaining 20,000 packs of Acetylsalicylic acid 75 mg tablets for your PO 25-04418 (ICRC order, AMEX project 20252275) is delayed due to a breakdown of the blister packaging line.

Revised release date: 9 October 2026 (originally 11 September 2026). FCA readiness is expected by 16 October 2026.

We apologise for the inconvenience and will inform you immediately if the date can be brought forward.

Best regards,
Customer Service
Galena Pharma GmbH, Graz""")

# ---------------------------------------------------------------- 16: UNICEF damaged cartons (forwarder)
t16 = d(9, 10, 11, 20)
write("16_unicef_damaged_cartons.eml", msg_id="<unicef-cph-0910@unicef.example>",
      sender="Lars Nielsen <lnielsen@unicef.example>", to=ADDR["jmarkovic"],
      subject="Damaged goods on receipt - PO 43210988 - ORS low osmolarity - project 20260127",
      when=t16, body="""Dear Jelena,

The shipment for PO 43210988 (your project 20260127) was received at the UNICEF Supply Division warehouse in Copenhagen on 9 September 2026.

On receipt, 2 of the 3 pallets had collapsed corners and 14 cartons of ORS low osmolarity sachets (20.5 g, 100 sachets per carton) were crushed; around 180 sachets were torn and the powder had spilled. The damage was noted on the CMR by our receiving clerk. The pallets were not stretch-wrapped when delivered by TransAlp Freight.

Photos and the annotated CMR are attached. Please arrange replacement of the 14 cartons and advise how you will handle the claim with the carrier.

Kind regards,
Lars Nielsen
Warehouse Quality Coordinator
UNICEF Supply Division""", attachments=["photos_damaged_pallets.zip", "CMR_annotated.pdf"])

# ---------------------------------------------------------------- 17: internal wrong quotation
t17 = d(9, 17, 14, 12)
write("17_internal_wrong_quotation.eml", msg_id="<amex-20260355-wq@amex-healthcare.com>",
      sender=ADDR["lhofer"], to=ADDR["quality"], cc=ADDR["jmarkovic"],
      subject="Deviation - wrong pack size in offer to UNFPA - project 20260355",
      when=t17, body="""Dear Quality team,

I would like to report a deviation on project 20260355 (UNFPA, Misoprostol 200 mcg tablets).

Our offer of 12 August quoted the supplier price for a pack of 100 tablets but described the item as a pack of 1,000 tablets. UNFPA issued the PO based on the 1,000-tablet description. The supplier (Medopharm) will only deliver at the correct price, which leaves a difference of EUR 2,350 that AMEX has to absorb to honour the PO.

Root cause: the quotation was prepared from an old price list and the pack size was not cross-checked against the supplier offer before submission.

We will fulfil the order at the quoted price. I suggest we add a second-person check of pack size and unit price for all pharma quotations above EUR 10,000.

Best regards,
""" + AMEX_SIG["lhofer"])

# ---------------------------------------------------------------- 18: supplier safety notice (no recall)
t18 = d(9, 18, 9, 30)
write("18_supplier_safety_notice_resuscitator.eml", msg_id="<ventora-fsn-0918@ventora-medical.example>",
      sender="Ventora Medical Vigilance <vigilance@ventora-medical.example>", to=ADDR["pweiss"],
      subject="Important product information - BVM resuscitator adult 1.5 L - batches 25K07, 25K09",
      when=t18, body="""Dear Customer,

Ventora Medical is issuing this important product information (Field Safety Notice FSN-2026-014) for the BVM Resuscitator, Adult, 1.5 L bag with size 5 mask, batches 25K07 and 25K09.

A limited number of units in these batches may have been assembled without the rear air-intake valve. Without this valve the delivered oxygen concentration (FiO2) can be lower than stated in the Instructions for Use; ventilation itself is not affected. No product needs to be returned. Users should perform the pre-use functional check described in section 4 of the IFU and discard any unit where the rear valve is missing.

Our distribution records show that 600 units of batch 25K09 were shipped to AMEX Healthcare GmbH (project 20252582, customer UNDP). Please forward this notice to your customer and return the confirmation of receipt.

Kind regards,
Vigilance Department
Ventora Medical Ltd""", attachments=["FSN-2026-014.pdf"])

# ---------------------------------------------------------------- 19: non-DCR logistics coordination
t19 = d(9, 21, 14, 23)
write("19_logistics_collection_not_dcr.eml", msg_id="<amex-shp26-00913@amex-healthcare.com>",
      sender=ADDR["jmarkovic"], to="GVA BSC Procurement Services <gva_procurement@icrc.example>",
      subject="RE: ICRC AME01AT/GVA26/029431 / INV26-01340 [Request 202514611] - collection",
      when=t19, body="""Dear Miljan,

I am happy to revert with the shipping documents for the remaining delivery under this order.

Goods are ready for collection at:
Pharmalager Hagenbrunn GmbH
c/o AMEX Healthcare
Dietersdorferstraße 10-18, Halle I/J - Rampe 27
2102 Hagenbrunn, Austria

Reference number for this collection: AMEX 20252275 / SHP26-00913.

Please make sure that we are contacted at least 48h prior to collection.

Many thanks and with kind regards,
""" + AMEX_SIG["jmarkovic"], attachments=["Packing_list_SHP26-00913.pdf", "Invoice_INV26-01340.pdf"])

# ---------------------------------------------------------------- 20: German warehouse deviation
t20 = d(9, 22, 8, 17)
write("20_warehouse_goods_receipt_german.eml", msg_id="<phl-we-26-4471@pharmalager-hagenbrunn.example>",
      sender="Wareneingang Pharmalager Hagenbrunn <wareneingang@pharmalager-hagenbrunn.example>", to=ADDR["jmarkovic"],
      cc=ADDR["quality"], subject="Abweichung Wareneingang WE-26-4471 - Projekt 20260412 - Datenlogger fehlt",
      when=t20, body="""Sehr geehrte Frau Markovic,

beim Wareneingang WE-26-4471 am 21.09.2026 (Projekt 20260412, Lieferant Kovač Pharma d.o.o., Oxytocin 10 IE/ml Injektionslösung, 2–8 °C, Charge KP2608-11, 3 Paletten) wurde festgestellt:

1. In Palette 3 wurde kein Temperaturdatenlogger gefunden, obwohl laut Lieferschein pro Palette ein Logger beigelegt sein sollte.
2. Zwei Kartons der Palette 3 sind an der Ecke eingedrückt; die Primärverpackung ist unbeschädigt.

Die Ware wurde im Kühlbereich gesperrt (Status: Quarantäne). Bitte klären Sie mit dem Lieferanten, ob Temperaturdaten für Palette 3 vorliegen, und teilen Sie uns die Freigabeentscheidung mit.

Mit freundlichen Grüßen
Team Wareneingang
Pharmalager Hagenbrunn GmbH""", attachments=["WE-26-4471_Fotos.pdf"])

print(len(list(OUT.glob("*.eml"))), "files written to", OUT)
