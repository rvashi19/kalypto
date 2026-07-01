# ruff: noqa: E501
"""ITC-HS chapter index (2-digit) — official chapter titles.

Seeds the 2-digit chapter rows so the master has the full chapter hierarchy and
"Browse Chapters" / chapter counts work. Idempotent via the import pipeline.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.hsn_import import import_hsn_snapshot

CHAPTERS: dict[str, str] = {
    "01": "Live animals",
    "02": "Meat and edible meat offal",
    "03": "Fish and crustaceans, molluscs and other aquatic invertebrates",
    "04": "Dairy produce; birds' eggs; natural honey; edible products of animal origin",
    "05": "Products of animal origin, not elsewhere specified or included",
    "06": "Live trees and other plants; bulbs, roots; cut flowers and ornamental foliage",
    "07": "Edible vegetables and certain roots and tubers",
    "08": "Edible fruit and nuts; peel of citrus fruit or melons",
    "09": "Coffee, tea, mate and spices",
    "10": "Cereals",
    "11": "Products of the milling industry; malt; starches; inulin; wheat gluten",
    "12": "Oil seeds and oleaginous fruits; miscellaneous grains, seeds and fruit; industrial or medicinal plants; straw and fodder",
    "13": "Lac; gums, resins and other vegetable saps and extracts",
    "14": "Vegetable plaiting materials; vegetable products not elsewhere specified",
    "15": "Animal or vegetable fats and oils and their cleavage products; prepared edible fats; animal or vegetable waxes",
    "16": "Preparations of meat, of fish or of crustaceans, molluscs or other aquatic invertebrates",
    "17": "Sugars and sugar confectionery",
    "18": "Cocoa and cocoa preparations",
    "19": "Preparations of cereals, flour, starch or milk; pastrycooks' products",
    "20": "Preparations of vegetables, fruit, nuts or other parts of plants",
    "21": "Miscellaneous edible preparations",
    "22": "Beverages, spirits and vinegar",
    "23": "Residues and waste from the food industries; prepared animal fodder",
    "24": "Tobacco and manufactured tobacco substitutes",
    "25": "Salt; sulphur; earths and stone; plastering materials, lime and cement",
    "26": "Ores, slag and ash",
    "27": "Mineral fuels, mineral oils and products of their distillation; bituminous substances; mineral waxes",
    "28": "Inorganic chemicals; compounds of precious metals, rare-earth metals, radioactive elements or isotopes",
    "29": "Organic chemicals",
    "30": "Pharmaceutical products",
    "31": "Fertilisers",
    "32": "Tanning or dyeing extracts; dyes, pigments, paints and varnishes; putty; inks",
    "33": "Essential oils and resinoids; perfumery, cosmetic or toilet preparations",
    "34": "Soap, washing and lubricating preparations, waxes, polishing preparations, candles, modelling pastes, dental waxes",
    "35": "Albuminoidal substances; modified starches; glues; enzymes",
    "36": "Explosives; pyrotechnic products; matches; pyrophoric alloys; certain combustible preparations",
    "37": "Photographic or cinematographic goods",
    "38": "Miscellaneous chemical products",
    "39": "Plastics and articles thereof",
    "40": "Rubber and articles thereof",
    "41": "Raw hides and skins (other than furskins) and leather",
    "42": "Articles of leather; saddlery and harness; travel goods, handbags and similar containers",
    "43": "Furskins and artificial fur; manufactures thereof",
    "44": "Wood and articles of wood; wood charcoal",
    "45": "Cork and articles of cork",
    "46": "Manufactures of straw, of esparto or of other plaiting materials; basketware and wickerwork",
    "47": "Pulp of wood or of other fibrous cellulosic material; recovered paper or paperboard",
    "48": "Paper and paperboard; articles of paper pulp, of paper or of paperboard",
    "49": "Printed books, newspapers, pictures and other products of the printing industry",
    "50": "Silk",
    "51": "Wool, fine or coarse animal hair; horsehair yarn and woven fabric",
    "52": "Cotton",
    "53": "Other vegetable textile fibres; paper yarn and woven fabrics of paper yarn",
    "54": "Man-made filaments; strip and the like of man-made textile materials",
    "55": "Man-made staple fibres",
    "56": "Wadding, felt and nonwovens; special yarns; twine, cordage, ropes and cables",
    "57": "Carpets and other textile floor coverings",
    "58": "Special woven fabrics; tufted textile fabrics; lace; tapestries; trimmings; embroidery",
    "59": "Impregnated, coated, covered or laminated textile fabrics; textile articles for industrial use",
    "60": "Knitted or crocheted fabrics",
    "61": "Articles of apparel and clothing accessories, knitted or crocheted",
    "62": "Articles of apparel and clothing accessories, not knitted or crocheted",
    "63": "Other made-up textile articles; sets; worn clothing and worn textile articles; rags",
    "64": "Footwear, gaiters and the like; parts of such articles",
    "65": "Headgear and parts thereof",
    "66": "Umbrellas, walking sticks, seat-sticks, whips, riding-crops and parts thereof",
    "67": "Prepared feathers and down; artificial flowers; articles of human hair",
    "68": "Articles of stone, plaster, cement, asbestos, mica or similar materials",
    "69": "Ceramic products",
    "70": "Glass and glassware",
    "71": "Natural or cultured pearls, precious stones, precious metals; imitation jewellery; coin",
    "72": "Iron and steel",
    "73": "Articles of iron or steel",
    "74": "Copper and articles thereof",
    "75": "Nickel and articles thereof",
    "76": "Aluminium and articles thereof",
    "78": "Lead and articles thereof",
    "79": "Zinc and articles thereof",
    "80": "Tin and articles thereof",
    "81": "Other base metals; cermets; articles thereof",
    "82": "Tools, implements, cutlery, spoons and forks, of base metal; parts thereof",
    "83": "Miscellaneous articles of base metal",
    "84": "Nuclear reactors, boilers, machinery and mechanical appliances; parts thereof",
    "85": "Electrical machinery and equipment and parts thereof; sound and television recorders/reproducers",
    "86": "Railway or tramway locomotives, rolling-stock and parts; track fixtures; signalling equipment",
    "87": "Vehicles other than railway or tramway rolling-stock, and parts and accessories thereof",
    "88": "Aircraft, spacecraft, and parts thereof",
    "89": "Ships, boats and floating structures",
    "90": "Optical, photographic, measuring, checking, medical or surgical instruments; parts thereof",
    "91": "Clocks and watches and parts thereof",
    "92": "Musical instruments; parts and accessories of such articles",
    "93": "Arms and ammunition; parts and accessories thereof",
    "94": "Furniture; bedding, mattresses; lamps and lighting fittings; prefabricated buildings",
    "95": "Toys, games and sports requisites; parts and accessories thereof",
    "96": "Miscellaneous manufactured articles",
    "97": "Works of art, collectors' pieces and antiques",
    "98": "Project imports; laboratory chemicals; passengers' baggage and personal imports (India)",
    "99": "Services (SAC) and miscellaneous",
}


def seed_chapters(*, session: Session, source_version: str = "itchs-chapters") -> dict[str, int]:
    """Idempotently upsert all 2-digit chapter rows. Does not overwrite richer rows."""
    records = [{"code": code, "description": name} for code, name in CHAPTERS.items()]
    payload = json.dumps({"records": records}).encode("utf-8")
    result = import_hsn_snapshot(
        session=session,
        raw_bytes=payload,
        import_type="json",
        source_name="ITC-HS Section/Chapter index (CBIC/DGFT)",
        source_url="https://www.cbic.gov.in/",
        source_document_title="ITC-HS chapter index",
        source_document_date=None,
        source_version=source_version,
    )
    return {
        "seen": result.job.records_seen,
        "created": result.job.records_created,
        "updated": result.job.records_updated,
    }
