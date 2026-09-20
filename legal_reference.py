"""India-specific legal references for follow-up questions about the law
behind a contract.

The Ollama model used for chat is small, so statutory citations must never be
left to generation. This module deterministically maps a question's topic to
the relevant Indian statutes and sections (IPC/BNS + substantive contract law),
and the LLM is then told to cite ONLY these references verbatim.
"""

# Common IPC -> BNS (Bharatiya Nyaya Sanhita, 2023, in force 01-Jul-2024)
# equivalents, shown as a reference note whenever criminal law is discussed.
IPC_BNS_CHEATSHEET = (
    "Note: the Indian Penal Code (IPC, 1860) was replaced on 1 July 2024 by the "
    "Bharatiya Nyaya Sanhita (BNS), 2023. Common equivalents: IPC 378 (theft) -> "
    "BNS 303; 403 (dishonest misappropriation) -> 304; 405 (criminal breach of "
    "trust) -> 316; 415 (cheating) -> 318; 420 (cheating and dishonestly inducing "
    "delivery of property) -> 318(4); 463-471 (forgery) -> 336-341; 499 (defamation) "
    "-> 356; 503 (criminal intimidation) -> 351; 323 (voluntarily causing hurt) -> 115."
)

# General contract-law backbone always cited for questions about enforceability,
# breach or remedies (civil side).
GENERAL_CONTRACT = (
    "- **Indian Contract Act, 1872** — s.10 (valid contract), ss.15-19 (coercion, "
    "undue influence, fraud, misrepresentation and a voidable contract), s.23 (unlawful "
    "consideration/object), s.27 (restraints of trade are void), s.28 (agreements in "
    "restraint of legal proceedings are void), s.56 (impossibility / frustration), "
    "ss.73-74 (compensation and penalty for breach).\n"
    "- **Specific Relief Act, 1963** — ss.14 & 20 (specific performance, discretionary), "
    "ss.36-42 (injunctions, declaratory relief).\n"
    "- **Limitation Act, 1963** — s.3 read with the Schedule: 3 years for most "
    "contract suits, 12 years for immovable-property possession.\n"
    "- **Code of Civil Procedure, 1908** — Order XXXVII (summary suit for money debts) "
    "and Order XXXIX (temporary injunctions)."
)

# Topic -> statutes/sections, matched by keywords in the question.
ROUTES = [
    {
        "topic": "Fraud, cheating or forgery",
        "keywords": ["fraud", "cheat", "cheating", "420", "forged", "forgery",
                     "bogus", "fake", "induce", "deceiv", "dishonest", "con man"],
        "sections": [
            "- **Indian Contract Act, 1872** — ss.17 & 19: fraud makes a contract "
            "voidable at the option of the defrauded party.",
            "- **IPC s.415 & 420 / BNS ss.318 & 318(4)** — cheating and dishonestly "
            "inducing delivery of property; a criminal remedy by FIR / police complaint.",
            "- **IPC ss.463-471 / BNS ss.336-341** — forgery of documents (if "
            "documents were fabricated).",
        ],
    },
    {
        "topic": "Theft, misappropriation or embezzlement",
        "keywords": ["theft", "steal", "stolen", "misappropriat", "embezzle",
                     "diversion", "abscond", "misuse of funds", "pocket"],
        "sections": [
            "- **IPC s.378 / BNS s.303** — theft.",
            "- **IPC s.403 / BNS s.304** — dishonest misappropriation of property.",
            "- **IPC s.405 / BNS s.316** — criminal breach of trust (where property "
            "was entrusted) — a criminal remedy alongside civil recovery.",
            "- **Indian Contract Act, 1872** — ss.73-74: civil recovery of loss and "
            "stipulated damages from the wrongdoer.",
        ],
    },
    {
        "topic": "Non-payment, breach and recovery of money",
        "keywords": ["pay", "unpaid", "non-payment", "default", "breach", "recover",
                     "damages", "loss", "restitution", "sue", "refund", "arrears",
                     "outstanding", "invoice", "overdue"],
        "sections": [
            "- **Indian Contract Act, 1872** — ss.73-74: compensation for breach and "
            "enforcement of a reasonable pre-agreed penalty.",
            "- **Specific Relief Act, 1963** — ss.14 & 20: specific performance is "
            "discretionary and generally not granted for money sums.",
            "- **Limitation Act, 1963** — s.3: a suit for breach must be filed within "
            "3 years of the breach (non-payment).",
            "- **Code of Civil Procedure, 1908** — Order XXXVII: summary suit for "
            "undisputed money claims.",
        ],
    },
    {
        "topic": "Cheque dishonour (payment by cheque)",
        "keywords": ["cheque", "check bounce", "bounced", "dishonour", "139", "138",
                     "returned unpaid"],
        "sections": [
            "- **Negotiable Instruments Act, 1881** — s.138: dishonour of a cheque "
            "for insufficiency of funds (criminal liability); s.142 (filing within "
            "1 month of notice), s.143 (summary trial), s.148 (interim compensation).",
            "- **Negotiable Instruments Act, 1881** — s.80: the payee may also claim "
            "interest on a dishonoured promissory note or bill.",
        ],
    },
    {
        "topic": "Confidentiality, NDA and trade secrets",
        "keywords": ["confidential", "nda", "non-disclosure", "trade secret", "secrec",
                     "proprietary info", "leak"],
        "sections": [
            "- **Indian Contract Act, 1872** — ss.73-74: damages for breach of the "
            "confidentiality obligation; s.27 relevant if any post-term restraint is "
            "added (restraints of trade are void).",
            "- **Information Technology Act, 2000** — s.72A: disclosure of information "
            "obtained under a lawful contract in breach of the agreement (criminal "
            "liability if it causes wrongful loss) — a common NDA remedy.",
            "- **Copyright Act, 1957** — ss.51 & 54-58: if the secret includes "
            "copyrightable documents or source.",
        ],
    },
    {
        "topic": "Non-compete and restraint of trade",
        "keywords": ["non-compete", "restraint", "competition", "poach", "solicit",
                     "exclusiv", "not to work", "rival"],
        "sections": [
            "- **Indian Contract Act, 1872** — s.27: EVERY agreement in restraint of "
            "trade is void. Post-employment non-compete restrictions are generally "
            "unenforceable in India unless they are a sale-of-goodwill exception.",
            "- **Indian Contract Act, 1872** — ss.73-74 for the (limited) protection "
            "a non-solicitation clause can give through damages; injunctions only "
            "under narrow exceptions.",
        ],
    },
    {
        "topic": "Privacy and personal data",
        "keywords": ["privacy", "personal data", "dpdp", "gdpr", "data protect",
                     "sensitive", "biometric", "collection of data", "consent"],
        "sections": [
            "- **Digital Personal Data Protection Act, 2023** — consent-based "
            "processing of personal data, notice, purpose limitation and data-fiduciary "
            "obligations (as operationalised).",
            "- **Information Technology Act, 2000** — s.43 (unauthorised access/damage "
            "to computers) and s.43A (compensation for negligently leaking personal "
            "data) — the pre-DPDP fallback.",
        ],
    },
    {
        "topic": "Intellectual property (copyright / trademark / patent)",
        "keywords": ["copyright", "trademark", "patent", "infring", "ipl", "intellectual",
                     "logo", "brand name", "source code", "design"],
        "sections": [
            "- **Copyright Act, 1957** — s.51 (infringement), ss.54-58 (civil remedies, "
            "accounts, Anton Piller orders), s.63 (criminal penalties).",
            "- **Trade Marks Act, 1999** — s.29 (infringement), ss.101-103 + s.135 "
            "(criminal and civil remedies).",
            "- **Patents Act, 1970** — s.48 (exclusive rights), ss.105-110 (infringement "
            "and remedies).",
        ],
    },
    {
        "topic": "Indemnity, limitation of liability and penalties",
        "keywords": ["indemn", "cap", "limitation of liable", "penalty", "liquidated",
                     "damages cap", "liability", "hold harmless"],
        "sections": [
            "- **Indian Contract Act, 1872** — ss.124-125: contract of indemnity and "
            "the indemnified party's rights.",
            "- **Indian Contract Act, 1872** — s.74: a stipulated penalty is enforced "
            "only to the extent of a REASONABLE compensation for the loss, not as a "
            "windfall; unreasonable caps can be struck down.",
        ],
    },
    {
        "topic": "Governing law, jurisdiction and dispute resolution",
        "keywords": ["govern", "jurisdiction", "arbitrat", "dispute", "forum", "court",
                     "which law", "law applies", "applicable law", "law of the document",
                     "bad faith"],
        "sections": [
            "- **Indian Contract Act, 1872** — s.28: agreements that oust the "
            "jurisdiction of courts or restrict legal proceedings are VOID (subject "
            "to the domestic-arbitration carve-out).",
            "- **Arbitration and Conciliation Act, 1996** — s.7 (valid arbitration "
            "agreement), s.34 (setting aside an award — narrow grounds), ss.35-37.",
            "- **Code of Civil Procedure, 1908** — s.20 and Order XXXIX: where a suit "
            "lies and interim injunctions.",
        ],
    },
    {
        "topic": "Force majeure and frustration",
        "keywords": ["force majeure", "act of god", "frustrat", "impossible", "epidemic",
                     "pandemic", "covid", "strike", "lockout", "unavoidable"],
        "sections": [
            "- **Indian Contract Act, 1872** — s.56: if performance becomes impossible "
            "or unlawful after the contract is made, the agreement becomes void and "
            "the court decides compensation; this is the general force-majeure "
            "backstop when no force-majeure clause exists.",
        ],
    },
    {
        "topic": "Sale of goods, warranties and refunds",
        "keywords": ["goods", "warrant", "defective", "refund", "buyer", "seller",
                     "consumer", "quality", "specification", "deliver"],
        "sections": [
            "- **Sale of Goods Act, 1930** — ss.12-17 (conditions & warranties), "
            "ss.55-58 (rights of an unpaid seller, damages for non-delivery), ss.59-61.",
            "- **Consumer Protection Act, 2019** — s.2(11) (consumer), ss.38-39 "
            "(complaint and redressal before the Consumer Commission if the goods or "
            "services are bought for consideration).",
        ],
    },
    {
        "topic": "Rent, lease and tenancy",
        "keywords": ["rent", "lease", "tenan", "landlord", "evict", "notice period",
                     "vacat", "occupant", "premises"],
        "sections": [
            "- **Transfer of Property Act, 1882** — ss.105-116: law of leases (s.106: "
            "termination notice; s.111: modes of lease determination).",
            "- **State rent-control legislation / Model Tenancy Act, 2021** — most "
            "states have their own Rent Control Acts; the precise rules vary by state.",
        ],
    },
    {
        "topic": "Employment, termination and retrenchment",
        "keywords": ["employee", "employer", "salary", "retrench", "termination",
                     "notice period", "gratuity", "pf", "probation", "resign",
                     "dismiss", "layoff"],
        "sections": [
            "- **Industrial Disputes Act, 1947** — ss.25F-25O: procedure for "
            "termination, retrenchment and layoff of workmen.",
            "- **Payment of Gratuity Act, 1972** — s.4 (gratuity after 5 years); "
            "**Employees' PF Act, 1952** — contributions payable.",
            "- **Shops & Establishments Acts (state)** — leave, working hours and "
            "termination-notice rules by state.",
        ],
    },
    {
        "topic": "Guarantee, surety and co-obligation",
        "keywords": ["guarantor", "surety", "guarantee", "co-signer", "personal guarantee"],
        "sections": [
            "- **Indian Contract Act, 1872** — ss.126-128 (guarantee and the surety's "
            "co-extensive liability) and ss.133-144 (when the surety is discharged).",
        ],
    },
    {
        "topic": "Partnership and business structure",
        "keywords": ["partnership", "partner", "llp", "company", "incorporat",
                     "moa", "aoa", "director", "shareholder"],
        "sections": [
            "- **Companies Act, 2013** — limited liability and the MOA/AOA; s.34 "
            "(false statements), s.447 (fraud), ss.448-451 (penalties).",
            "- **Partnership Act, 1932** — ss.31-42 (authority and dissolution); "
            "**LLP Act, 2008** s.23 for LLPs.",
        ],
    },
]

# Keywords that indicate the user is actually asking about the *law* behind the
# document, so legal references should be attached even if no topic route fires.
INTENT_KEYWORDS = [
    "what law", "which law", "law applies", "applicable law", "law of the",
    "legal", "illegal", "legally", "lawful", "unlawful", "statute", "ipc", "bns",
    "penal", "section", "act of parliament", "enforceable", "court", "sue",
    "prosecut", "police", "crime", "criminal", "offence", "offense", "allowed",
    "permitted", "prohibit", "punish", "is this", "can they", "can he", "can she",
    "against the law", "right to", "entitled", "rule", "regulation", "govt",
]


def _match_score(route, text: str) -> int:
    low = text.lower()
    return sum(1 for kw in route["keywords"] if kw in low)


def _detect_law_intent(question: str) -> bool:
    low = question.lower()
    if any(kw in low for kw in INTENT_KEYWORDS):
        return True
    return any(_match_score(r, question) > 0 for r in ROUTES)


def law_references_for(question: str, clause_text: str = "") -> str:
    """Return a markdown block of India-specific legal references for the
    question, or an empty string when the question is not about the law.

    Always includes the general contract-law backbone, plus up to three
    matched topic routes, plus the IPC->BNS cheat sheet when relevant.
    """
    if not _detect_law_intent(question):
        return ""

    scored = sorted(
        ((_match_score(r, question + " " + clause_text), r) for r in ROUTES),
        key=lambda t: t[0],
        reverse=True,
    )
    picked = [r for s, r in scored if s > 0][:3]

    parts = [GENERAL_CONTRACT]
    for r in picked:
        parts.append(f"**{r['topic']}**\n" + "\n".join(r["sections"]))
    parts.append(IPC_BNS_CHEATSHEET)
    return "\n\n".join(parts)