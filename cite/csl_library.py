"""Structured CSL-JSON for the 33 references, in citation order."""
import json

def A(*names):
    out = []
    for n in names:
        if isinstance(n, dict):
            out.append(n); continue
        given, family = n.rsplit(" ", 1) if "|" not in n else n.split("|")
        out.append({"family": family, "given": given})
    return out

def J(title, authors, journal, year, vol=None, issue=None, page=None, doi=None, short=None):
    d = {"type": "article-journal", "title": title, "author": authors, "container-title": journal,
         "issued": {"date-parts": [[year]]}}
    if short: d["container-title-short"] = short
    if vol: d["volume"] = str(vol)
    if issue: d["issue"] = str(issue)
    if page: d["page"] = page
    if doi: d["DOI"] = doi
    return d

LIB = [
 J("Effects of workload, work complexity, and repeated alerts on alert fatigue in a clinical decision support system",
   A("J. S.|Ancker", "A.|Edwards", "S.|Nosal", "D.|Hauser", "E.|Mauer", "R.|Kaushal"),
   "BMC Medical Informatics and Decision Making", 2017, 17, None, "36", "10.1186/s12911-017-0430-8", "BMC Med. Informat. Decis. Making"),
 J("External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients",
   A("Andrew|Wong", "Erkin|Otles", "John P.|Donnelly", "Andrew|Krumm", "Jeffrey|McCullough", "Olivia|DeTroyer-Cooley",
     "Justin|Pestrue", "Marie|Phillips", "Judy|Konye", "Carleen|Penoza", "Muhammad|Ghous", "Karandeep|Singh"),
   "JAMA Internal Medicine", 2021, 181, 8, "1065-1070", "10.1001/jamainternmed.2021.2626", "JAMA Intern. Med."),
 J("A systematic review of clinicians' acceptance and use of clinical decision support systems over time",
   A("N.|Newton", "A.|Bamgboje-Ayodele", "R.|Forsyth", "A.|Tariq", "M. T.|Baysari"),
   "npj Digital Medicine", 2025, 8, None, "309", "10.1038/s41746-025-01662-7", "npj Digit. Med."),
 J("Clinical evaluation of a machine learning–based early warning system for patient deterioration",
   A("Amol A.|Verma", "Therese A.|Stukel", "Michael|Colacci", "Shirley|Bell", "Jonathan|Ailon", "Jan O.|Friedrich",
     "Joshua|Murray", "Sebnem|Kuzulugil", "Zhen|Yang", "Yuna|Lee", "Chloe|Pou-Prom", "Muhammad|Mamdani"),
   "Canadian Medical Association Journal", 2024, 196, 30, "E1027-E1037", "10.1503/cmaj.240132", "Can. Med. Assoc. J."),
 J("Real-time surveillance system for patient deterioration: A pragmatic cluster-randomized controlled trial",
   A("Sarah C.|Rossetti", "Patricia C.|Dykes", "Chris|Knaplund", "Sandy|Cho", "Jennifer|Withall", "Graham|Lowenthal",
     "David|Albers", "Rachel Y.|Lee", "Haomiao|Jia", "Suzanne|Bakken", "Min-Jeoung|Kang", "Frank Y.|Chang", "Li|Zhou",
     "David W.|Bates", "Temiloluwa|Daramola", "Fang|Liu", "Jessica|Schwartz-Dillard", "Mai|Tran",
     "Syed Mohtashim Abbas|Bokhari", "Jennifer|Thate", "Kenrick D.|Cato"),
   "Nature Medicine", 2025, 31, 6, "1895-1902", "10.1038/s41591-025-03609-7", "Nature Med."),
 J("Prospective, multi-site study of patient outcomes after implementation of the TREWS machine learning-based early warning system for sepsis",
   A("Roy|Adams", "Katharine E.|Henry", "Anirudh|Sridharan", "Hossein|Soleimani", "Andong|Zhan", "Nishi|Rawat",
     "Lauren|Johnson", "David N.|Hager", "Sara E.|Cosgrove", "Andrew|Markowski", "Eili Y.|Klein", "Edward S.|Chen",
     "Mustapha O.|Saheed", "Maureen|Henley", "Sheila|Miranda", "Katrina|Houston", "Robert C.|Linton",
     "Anushree R.|Ahluwalia", "Albert W.|Wu", "Suchi|Saria"),
   "Nature Medicine", 2022, 28, 7, "1455-1460", "10.1038/s41591-022-01894-0", "Nature Med."),
 J("2023 ACC/AHA/ACCP/HRS guideline for the diagnosis and management of atrial fibrillation: A report of the American College of Cardiology/American Heart Association Joint Committee on Clinical Practice Guidelines",
   A("José A.|Joglar", "Mina K.|Chung", "Anastasia L.|Armbruster", "Emelia J.|Benjamin", "Janice Y.|Chyou",
     "Edmond M.|Cronin", "Anita|Deswal", "Lee L.|Eckhardt", "Zachary D.|Goldberger", "Rakesh|Gopinathannair"),
   "Circulation", 2024, 149, 1, "e1-e156", "10.1161/CIR.0000000000001193"),
 J("2024 ESC guidelines for the management of atrial fibrillation developed in collaboration with the European Association for Cardio-Thoracic Surgery (EACTS)",
   A("Isabelle C.|Van Gelder", "Michiel|Rienstra", "Karina V.|Bunting", "Ruben|Casado-Arroyo", "Valeria|Caso",
     "Harry J. G. M.|Crijns", "Tom J. R.|De Potter", "Jeremy|Dwight", "Luigina|Guasti", "Thorsten|Hanke", "Tiny|Jaarsma"),
   "European Heart Journal", 2024, 45, 36, "3314-3414", "10.1093/eurheartj/ehae176", "Eur. Heart J."),
 J("Design science in information systems research", A("Alan R.|Hevner", "Salvatore T.|March", "Jinsoo|Park", "Sudha|Ram"),
   "MIS Quarterly", 2004, 28, 1, "75-105", None, "MIS Quart."),
 J("A design science research methodology for information systems research",
   A("Ken|Peffers", "Tuure|Tuunanen", "Marcus A.|Rothenberger", "Samir|Chatterjee"),
   "Journal of Management Information Systems", 2007, 24, 3, "45-77", None, "J. Manage. Inf. Syst."),
 J("ADEPTflex—Supporting dynamic changes of workflows without losing control", A("Manfred|Reichert", "Peter|Dadam"),
   "Journal of Intelligent Information Systems", 1998, 10, 2, "93-129", "10.1023/A:1008604709862", "J. Intell. Inf. Syst."),
 J("Correctness criteria for dynamic changes in workflow systems—A survey", A("Stefanie|Rinderle", "Manfred|Reichert", "Peter|Dadam"),
   "Data & Knowledge Engineering", 2004, 50, 1, "9-34", None, "Data Knowl. Eng."),
 J("Change patterns and change support features—Enhancing flexibility in process-aware information systems",
   A("Barbara|Weber", "Manfred|Reichert", "Stefanie|Rinderle-Ma"),
   "Data & Knowledge Engineering", 2008, 66, 3, "438-466", "10.1016/j.datak.2008.05.001", "Data Knowl. Eng."),
 {"type": "book", "title": "Enabling Flexibility in Process-Aware Information Systems: Challenges, Methods, Technologies",
  "author": A("Manfred|Reichert", "Barbara|Weber"), "publisher": "Springer", "publisher-place": "Berlin, Germany",
  "issued": {"date-parts": [[2012]]}, "DOI": "10.1007/978-3-642-30409-5"},
 {"type": "report", "title": "Business Process Model and Notation (BPMN), Version 2.0.2",
  "author": [{"literal": "Object Management Group"}], "publisher": "Object Management Group", "publisher-place": "Milford, MA, USA",
  "issued": {"date-parts": [[2014]]}},
 {"type": "report", "title": "Decision Model and Notation (DMN), Version 1.3",
  "author": [{"literal": "Object Management Group"}], "publisher": "Object Management Group", "publisher-place": "Milford, MA, USA",
  "issued": {"date-parts": [[2019]]}},
 {"type": "paper-conference", "title": "DECLARE: Full support for loosely-structured processes",
  "author": [{"family": "Pesic", "given": "M."}, {"family": "Schonenberg", "given": "H."},
             {"family": "Aalst", "given": "W. M. P.", "non-dropping-particle": "van der"}],
  "container-title": "Proceedings of the 11th IEEE International Enterprise Distributed Object Computing Conference (EDOC)",
  "page": "287-298", "issued": {"date-parts": [[2007]]}, "DOI": "10.1109/EDOC.2007.4384001"},
 J("Flexible guideline-based patient careflow systems",
   A("S.|Quaglini", "M.|Stefanelli", "G.|Lanzola", "V.|Caporusso", "S.|Panzarasa"),
   "Artificial Intelligence in Medicine", 2001, 22, 1, "65-80", None, "Artif. Intell. Med."),
 J("A holistic environment for the design and execution of self-adaptive clinical pathways",
   A("D.|Alexandrou", "I.|Skitsas", "G.|Mentzas"),
   "IEEE Transactions on Information Technology in Biomedicine", 2011, 15, 1, "108-118", "10.1109/TITB.2010.2074205", "IEEE Trans. Inf. Technol. Biomed."),
 J("CONFlexFlow: Integrating flexible clinical pathways into clinical decision support systems using context and rules",
   A("Wen|Yao", "Akhil|Kumar"), "Decision Support Systems", 2013, 55, 2, "499-515", "10.1016/j.dss.2012.10.008", "Decis. Support Syst."),
 J("Validation of a modified early warning score in medical admissions",
   A("C. P.|Subbe", "M.|Kruger", "P.|Rutherford", "L.|Gemmel"), "QJM: An International Journal of Medicine", 2001, 94, 10, "521-526",
   "10.1093/qjmed/94.10.521", "QJM"),
 J("SMART on FHIR: A standards-based, interoperable apps platform for electronic health records",
   A("Joshua C.|Mandel", "David A.|Kreda", "Kenneth D.|Mandl", "Isaac S.|Kohane", "Rachel B.|Ramoni"),
   "Journal of the American Medical Informatics Association", 2016, 23, 5, "899-908", "10.1093/jamia/ocv189", "J. Amer. Med. Inform. Assoc."),
 {"type": "webpage", "title": "CDS Hooks Specification, Version 2.0", "author": [{"literal": "HL7 International"}],
  "URL": "https://cds-hooks.hl7.org", "accessed": {"date-parts": [[2026, 11, 3]]}, "issued": {"date-parts": [[2022]]}},
 {"type": "report", "title": "Management of Alarm Systems for the Process Industries", "number": "ANSI/ISA-18.2-2016",
  "author": [{"literal": "International Society of Automation"}], "publisher": "International Society of Automation",
  "publisher-place": "Research Triangle Park, NC, USA", "issued": {"date-parts": [[2016]]}},
 {"type": "chapter", "title": "Semantics and analysis of DMN decision tables",
  "author": A("Diego|Calvanese", "Marlon|Dumas", "Ülari|Laurson", "Fabrizio M.|Maggi", "Marco|Montali", "Irene|Teinemaa"),
  "container-title": "Business Process Management", "collection-title": "Lecture Notes in Computer Science", "volume": "9850",
  "publisher": "Springer", "publisher-place": "Cham, Switzerland", "page": "217-233", "issued": {"date-parts": [[2016]]},
  "DOI": "10.1007/978-3-319-45348-4_13"},
 J("Semantics, analysis and simplification of DMN decision tables",
   A("Diego|Calvanese", "Marlon|Dumas", "Ülari|Laurson", "Fabrizio M.|Maggi", "Marco|Montali", "Irene|Teinemaa"),
   "Information Systems", 2018, 78, None, "112-125", "10.1016/j.is.2017.11.001", "Inf. Syst."),
 {"type": "paper-conference", "title": "QuickCheck: A lightweight tool for random testing of Haskell programs",
  "author": A("Koen|Claessen", "John|Hughes"),
  "container-title": "Proceedings of the 5th ACM SIGPLAN International Conference on Functional Programming (ICFP)",
  "page": "268-279", "issued": {"date-parts": [[2000]]}, "DOI": "10.1145/351240.351266"},
 J("Hypothesis: A new approach to property-based testing", A("David R.|MacIver", "Zac|Hatfield-Dodds"),
   "Journal of Open Source Software", 2019, 4, 43, "1891", "10.21105/joss.01891", "J. Open Source Softw."),
 J("An analysis and survey of the development of mutation testing", A("Yue|Jia", "Mark|Harman"),
   "IEEE Transactions on Software Engineering", 2011, 37, 5, "649-678", "10.1109/TSE.2010.62", "IEEE Trans. Softw. Eng."),
 {"type": "paper-conference", "title": "Kafka: A distributed messaging system for log processing",
  "author": A("Jay|Kreps", "Neha|Narkhede", "Jun|Rao"), "container-title": "Proceedings of the NetDB Workshop",
  "page": "1-7", "issued": {"date-parts": [[2011]]}},
 {"type": "report", "title": "Peraturan Menteri Kesehatan Nomor 24 Tahun 2022 tentang Rekam Medis [Minister of Health Regulation No. 24 of 2022 on Medical Records]",
  "author": [{"literal": "Kementerian Kesehatan Republik Indonesia"}], "publisher": "Kementerian Kesehatan Republik Indonesia",
  "publisher-place": "Jakarta, Indonesia", "issued": {"date-parts": [[2022]]}},
 {"type": "report", "title": "Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi [Law No. 27 of 2022 on Personal Data Protection]",
  "author": [{"literal": "Republik Indonesia"}], "publisher": "Republik Indonesia", "publisher-place": "Jakarta, Indonesia",
  "issued": {"date-parts": [[2022]]}},
 J("Dissecting racial bias in an algorithm used to manage the health of populations",
   A("Ziad|Obermeyer", "Brian|Powers", "Christine|Vogeli", "Sendhil|Mullainathan"),
   "Science", 2019, 366, 6464, "447-453", "10.1126/science.aax2342"),
]
assert len(LIB) == 33
_M = {30: 27, 27: 28, 28: 29, 29: 30}
_new = [None] * 33
for _i, _e in enumerate(LIB):
    _new[_M.get(_i + 1, _i + 1) - 1] = _e
LIB = _new

_NEW = [
 J("Early prediction of sepsis from clinical data: The PhysioNet/Computing in Cardiology Challenge 2019",
   A("Matthew A.|Reyna", "Christopher S.|Josef", "Russell|Jeter", "Supreeth P.|Shashikumar", "M. Brandon|Westover",
     "Shamim|Nemati", "Gari D.|Clifford", "Ashish|Sharma"),
   "Critical Care Medicine", 2020, 48, 2, "210-217", "10.1097/CCM.0000000000004145", "Crit. Care Med."),
 J("PhysioBank, PhysioToolkit, and PhysioNet: Components of a new research resource for complex physiologic signals",
   A("Ary L.|Goldberger", "Luis A. N.|Amaral", "Leon|Glass", "Jeffrey M.|Hausdorff", "Plamen Ch.|Ivanov", "Roger G.|Mark",
     "Joseph E.|Mietus", "George B.|Moody", "Chung-Kang|Peng", "H. Eugene|Stanley"),
   "Circulation", 2000, 101, 23, "e215-e220", "10.1161/01.CIR.101.23.e215"),
]
LIB = LIB[:30] + _NEW + LIB[30:]
assert len(LIB) == 35

if __name__ == "__main__":
    json.dump(LIB, open("cite/library.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(LIB), "items")
