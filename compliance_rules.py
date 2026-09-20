import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ComplianceRule:
    name: str
    description: str
    keywords: list[str]
    patterns: list[str]
    category: str = "General"
    severity: str = "high"  # high, medium, low


@dataclass
class RuleResult:
    rule: ComplianceRule
    status: str  # "pass", "fail", "missing"
    matched_text: Optional[str] = None
    explanation: str = ""


DEFAULT_RULES = [
    ComplianceRule(
        name="Parties Identification",
        description="Contract must identify the parties involved (names, addresses, or definitions).",
        keywords=["party", "parties", "between", "hereinafter", "referred to as"],
        patterns=[
            r"(?:between|by and between)\s+[A-Z][\w\s,]+(?:and|&)\s+[A-Z][\w\s,]+",
            r"(?:party|parties)\s+(?:named|identified|described)",
            r"(?:\"(?:client|company|contractor|vendor|supplier|provider|customer|user)\"|'(?:client|company|contractor|vendor|supplier|provider|customer|user)')",
        ],
        category="Structure",
        severity="high",
    ),
    ComplianceRule(
        name="Term / Duration",
        description="Contract must specify its duration or term length.",
        keywords=["term", "duration", "period", "effective date", "expir", "renewal"],
        patterns=[
            r"(?:term|duration|period)\s+(?:of|shall be)\s+\w+\s*(?:year|month|day|week)",
            r"(?:effective\s+date|commenc(?:e|ing)\s+date)",
            r"(?:expir|terminat)\s+(?:on|date|upon)",
            r"\d+\s*(?:year|month|day)s?\s*(?:from|after|beginning)",
        ],
        category="Structure",
        severity="high",
    ),
    ComplianceRule(
        name="Termination Clause",
        description="Contract must define how either party can terminate the agreement.",
        keywords=["terminat", "end", "cancel", "breach", "notice period", "cure period"],
        patterns=[
            r"terminat(?:e|ion|ed)\s+(?:this|the)\s+agreement",
            r"(?:either|any)\s+party\s+may\s+terminat",
            r"(?:upon|after)\s+\d+\s*(?:day|week|month|year)s?\s*(?:written\s+)?notice",
            r"cure\s+period",
            r"(?:for\s+)?convenience",
        ],
        category="Termination",
        severity="high",
    ),
    ComplianceRule(
        name="Confidentiality",
        description="Contract must include confidentiality or non-disclosure provisions.",
        keywords=["confidential", "non-disclosure", "NDA", "proprietary", "trade secret", "disclose"],
        patterns=[
            r"confidential(?:ity)?\s+(?:information|material|data)",
            r"non[-\s]disclosure",
            r"shall\s+(?:not|maintain)\s+(?:disclose|reveal|share)",
            r"trade\s+secret",
            r"proprietary\s+(?:information|material)",
        ],
        category="Data Protection",
        severity="high",
    ),
    ComplianceRule(
        name="Intellectual Property",
        description="Contract must address ownership and rights to intellectual property.",
        keywords=["intellectual property", "IP", "copyright", "patent", "trademark", "ownership", "work product"],
        patterns=[
            r"intellectual\s+property",
            r"(?:own|ownership)\s+(?:of\s+)?(?:all\s+)?(?:IP|intellectual property|work product|deliverables)",
            r"(?:copyright|patent|trademark|trade\s+secret)s?",
            r"work\s+product",
            r"(?:assign|transfer)\s+(?:all\s+)?(?:right|title|interest)",
        ],
        category="IP",
        severity="high",
    ),
    ComplianceRule(
        name="Limitation of Liability",
        description="Contract must cap or limit liability exposure.",
        keywords=["liability", "limit", "cap", "damages", "indirect", "consequential", "aggregate"],
        patterns=[
            r"(?:limit(?:ed|ation)?\s+(?:of\s+)?liability|liability\s+(?:shall\s+be\s+)?limit)",
            r"(?:shall\s+not\s+exceed|not\s+exceed)\s+(?:\$\w+|the\s+(?:total|aggregate|amount))",
            r"(?:in\s+no\s+event|under\s+no\s+circumstance)\s+shall",
            r"consequential\s+(?:damages|liability)",
            r"aggregate\s+(?:liability|amount|limit)",
        ],
        category="Risk",
        severity="medium",
    ),
    ComplianceRule(
        name="Indemnification",
        description="Contract must include indemnification or hold-harmless provisions.",
        keywords=["indemnif", "hold harmless", "defend", "reimburse", "compensate"],
        patterns=[
            r"indemnif(?:y|ication|ied)",
            r"hold\s+harmless",
            r"(?:shall|agree\s+to)\s+(?:defend|indemnif)",
            r"(?:against|from|for)\s+(?:any\s+)?(?:claim|loss|damage|liability|expense)",
        ],
        category="Risk",
        severity="medium",
    ),
    ComplianceRule(
        name="Governing Law",
        description="Contract must specify which jurisdiction's law governs.",
        keywords=["governing law", "jurisdiction", "applicable law", "laws of", "state of"],
        patterns=[
            r"govern(?:ed|ing)\s+(?:by|law)\s+(?:the\s+)?laws?\s+of",
            r"(?:subject\s+to|under)\s+(?:the\s+)?laws?\s+of\s+(?:the\s+)?(?:State|Commonwealth|Province)\s+of",
            r"applicable\s+law",
            r"(?:exclusive|sole)\s+jurisdiction",
        ],
        category="Dispute",
        severity="medium",
    ),
    ComplianceRule(
        name="Dispute Resolution",
        description="Contract must describe how disputes will be resolved (arbitration, mediation, litigation).",
        keywords=["dispute", "arbitrat", "mediat", "litigation", "forum", "venue", "resolution"],
        patterns=[
            r"(?:dispute|claim)\s+(?:resolution|shall\s+be\s+resolv)",
            r"(?:binding\s+)?arbitrat(?:e|ion)",
            r"mediat(?:e|ion)",
            r"(?:exclusive\s+)?(?:forum|venue|jurisdiction)\s+(?:shall\s+be|for)",
        ],
        category="Dispute",
        severity="medium",
    ),
    ComplianceRule(
        name="Force Majeure",
        description="Contract should address unforeseeable circumstances preventing performance.",
        keywords=["force majeure", "act of god", "unforeseeable", "pandemic", "natural disaster"],
        patterns=[
            r"force\s+majeure",
            r"act(?:s)?\s+of\s+god",
            r"(?:beyond|outside)\s+(?:the\s+)?(?:reasonable\s+)?control",
            r"(?:pandemic|epidemic|quarantine|lockdown)",
        ],
        category="Risk",
        severity="low",
    ),
    ComplianceRule(
        name="Payment Terms",
        description="Contract must specify payment amounts, schedules, and methods.",
        keywords=["payment", "compensation", "fee", "price", "invoice", "payable", "remittance"],
        patterns=[
            r"(?:shall\s+)?(?:pay|compensat)\s+(?:the\s+)?(?:sum\s+of\s+)?\$",
            r"(?:payment|compensation)\s+(?:shall\s+be|due|terms)",
            r"(?:net\s+)\d+\s*(?:day|days)",
            r"invoice\s+(?:shall\s+be|term|period)",
            r"(?:monthly|quarterly|annually|weekly)\s+(?:basis|payment)",
        ],
        category="Financial",
        severity="high",
    ),
    ComplianceRule(
        name="Data Protection / Privacy",
        description="Contract should address data protection and privacy obligations.",
        keywords=["data protection", "privacy", "GDPR", "personal data", "data subject", "processing"],
        patterns=[
            r"data\s+protection",
            r"personal\s+data",
            r"(?:GDPR|CCPA|privacy\s+(?:policy|regulation|law))",
            r"data\s+(?:subject|controller|processor|breach)",
            r"(?:protect|secure|encrypt|safeguard)\s+(?:personal|sensitive)\s+data",
        ],
        category="Data Protection",
        severity="high",
    ),
    ComplianceRule(
        name="Warranties",
        description="Contract should include warranty or representation statements.",
        keywords=["warrant", "represent", "guarantee", "ensure", "covenant"],
        patterns=[
            r"warrant(?:y|ies|s)?\s+(?:that|hereby|set\s+forth)",
            r"represent(?:s|ation)?\s+(?:and\s+covenant)?\s+that",
            r"(?:hereby\s+)?guarantee(?:s)?\s+(?:that|the)",
            r"(?:as\s+is|without\s+warranty|no\s+warranty)",
        ],
        category="Risk",
        severity="medium",
    ),
    ComplianceRule(
        name="Assignment / Transfer",
        description="Contract should address whether rights can be assigned or transferred.",
        keywords=["assign", "transfer", "delegate", "successor", "novation"],
        patterns=[
            r"(?:shall\s+)?(?:not\s+)?(?:assign|transfer|delegate)",
            r"(?:without|subject\s+to)\s+(?:the\s+)?(?:prior\s+)?(?:written\s+)?consent",
            r"(?:successor|assign(?:ee|or)|transferee)",
            r"novation",
        ],
        category="Structure",
        severity="low",
    ),
    ComplianceRule(
        name="Entire Agreement / Severability",
        description="Contract should include integration and severability clauses.",
        keywords=["entire agreement", "severability", "integration", "supersedes", "invalid", "unenforceable"],
        patterns=[
            r"(?:this\s+)?(?:constitutes?|contains?)\s+(?:the\s+)?(?:entire|complete)\s+agreement",
            r"severab(?:le|ility)",
            r"(?:supersedes?|replaces?)\s+(?:all\s+)?(?:prior|previous|earlier)",
            r"(?:if\s+any\s+)?(?:provision|clause|section)\s+(?:is|shall\s+be)\s+(?:held\s+)?(?:invalid|unenforceable|void)",
        ],
        category="Structure",
        severity="medium",
    ),
    ComplianceRule(
        name="Amendment / Modification",
        description="Contract should state whether (and how) it can be amended or modified.",
        keywords=["amend", "modify", "modification", "may be changed", "written consent"],
        patterns=[
            r"(?:no\s+)?amend(?:ment|ing|ed)?\s+(?:of|to)\s+this\s+agreement",
            r"(?:any\s+)?modification\s+(?:of|to)\s+this\s+agreement",
            r"(?:changes?\s+(?:to\s+)?this\s+agreement\s+(?:shall|must)\s+be\s+in\s+writing)",
            r"(?:this|the)\s+agreement\s+may\s+(?:be\s+)?(?:amended|modified)",
        ],
        category="Structure",
        severity="medium",
    ),
    ComplianceRule(
        name="Notices",
        description="Contract should specify how formal notices must be given to the parties.",
        keywords=["notices", "written notice", "registered mail", "email", "notice address"],
        patterns=[
            r"(?:notices?|any\s+notice)\s+(?:shall|must|will)\s+be\s+(?:given|sent|provided)",
            r"(?:in\s+writing|written\s+notice)\s+(?:by\s+)?(?:registered|certified|courier|hand)",
            r"notice\s+shall\s+be\s+deemed\s+(?:given|received)",
            r"(?:by\s+)?(?:registered|certified)\s+mail",
        ],
        category="Structure",
        severity="low",
    ),
    ComplianceRule(
        name="Independent Contractor",
        description="Contract should clarify the relationship (independent contractor vs employee).",
        keywords=["independent contractor", "not an employee", "no employment", "employee relationship", "subcontractor"],
        patterns=[
            r"independent\s+contractor",
            r"(?:shall|be)\s+(?:deemed\s+)?an\s+independent\s+contractor",
            r"(?:no\s+)?(?:employer|employee)\s+relationship",
            r"(?:not\s+an\s+employee|not\s+an\s+employer)",
            r"(?:no\s+)?agency\s+relation",
        ],
        category="Structure",
        severity="medium",
    ),
    ComplianceRule(
        name="Non-Solicitation / Non-Compete",
        description="Contract should address restrictive covenants like non-solicitation or non-compete.",
        keywords=["non-solicit", "non compete", "non-compete", "solicit", "restrictive covenant", "compete"],
        patterns=[
            r"non[-\s]?(?:solicit|compete)",
            r"shall\s+not\s+(?:solicit|compete|engage)",
            r"(?:restrictive\s+)?covenant",
            r"(?:during|after)\s+(?:the\s+)?(?:term|termination).{0,60}(?:solicit|compete)",
        ],
        category="Risk",
        severity="low",
    ),
    ComplianceRule(
        name="Insurance",
        description="Contract should state insurance coverage obligations.",
        keywords=["insurance", "coverage", "policy", "insured", "liability insurance"],
        patterns=[
            r"insurance\s+(?:coverage|policy|shall)",
            r"(?:shall\s+)?(?:maintain|procure|carry)\s+(?:the\s+)?(?:following\s+)?insurance",
            r"(?:workers\s+compensation|general\s+liability|professional\s+liability)\s+insurance",
            r"(?:certificate\s+of|proof\s+of)\s+insurance",
        ],
        category="Risk",
        severity="low",
    ),
    ComplianceRule(
        name="Auditing / Inspection Rights",
        description="Contract should grant rights to inspect books, records, or premises.",
        keywords=["audit", "inspect", "inspection", "books and records", "right to audit", "review rights"],
        patterns=[
            r"(?:right\s+to\s+)?(?:audit|inspect)(?:ing)?\s+(?:the\s+)?(?:books|records|accounts|premises)",
            r"(?:shall\s+)?(?:maintain|keep)\s+(?:accurate\s+)?books\s+and\s+records",
            r"audit\s+rights",
            r"(?:upon\s+)?(?:reasonable\s+)?notice.{0,40}(?:audit|inspection)",
        ],
        category="Financial",
        severity="low",
    ),
    ComplianceRule(
        name="Survival Clause",
        description="Contract should state which obligations survive termination.",
        keywords=["surviv", "continue in force", "survive termination", "continue to apply"],
        patterns=[
            r"(?:the\s+)?(?:provisions|obligations|terms)\s+(?:hereunder\s+)?(?:shall|will|continue)\s+to\s+survive",
            r"surviv(?:al|e)\s+(?:of|after|beyond|the)\s+termination",
            r"(?:continue\s+in\s+full\s+force\s+and\s+effect)",
            r"survive\s+(?:the\s+|any\s+)?termination",
        ],
        category="Structure",
        severity="high",
    ),
    ComplianceRule(
        name="Counterparts / Execution",
        description="Contract should include counterparts or electronic signature provisions.",
        keywords=["counterpart", "facsimile", "electronic signature", "digital signature", "may be executed"],
        patterns=[
            r"(?:executed|signed)\s+in\s+counterparts",
            r"counterpart",
            r"(?:may\s+be\s+executed|execution)\s+in\s+(?:one\s+or\s+more|two)\s+counterparts",
            r"(?:electronic|digital|facsimile|\bpdf\b)\s+signature",
        ],
        category="Structure",
        severity="low",
    ),
    ComplianceRule(
        name="Compliance with Laws",
        description="Contract should require compliance with applicable laws and regulations.",
        keywords=["comply with", "applicable laws", "laws and regulations", "legal requirements", "regulatory"],
        patterns=[
            r"(?:shall|agree(?:s)?)\s+to?\s+comply\s+with\s+(?:all\s+)?(?:applicable\s+)?(?:laws|regulations)",
            r"compliance\s+with\s+(?:all\s+)?(?:applicable\s+)?(?:laws|regulations|requirements)",
            r"(?:in\s+accordance\s+with|subject\s+to)\s+(?:all\s+)?(?:applicable\s+)?(?:laws|regulations)",
            r"legal\s+and\s+regulatory\s+requirements",
        ],
        category="Compliance",
        severity="medium",
    ),
    ComplianceRule(
        name="Renewal / Auto-Renewal",
        description="Contract should state how the term renews (if at all).",
        keywords=["renew", "renewal", "automatic renewal", "renew automatically", "notice of non-renewal"],
        patterns=[
            r"(?:shall\s+)?renew(?:al|ed)?\s+automatically",
            r"(?:automatic(?:ally)?\s+renewal|renewal\s+notice\s+period)",
            r"(?:term\s+)?(?:shall\s+be\s+(?:extended|continued))\s+(?:for\s+)?(?:an?\s+additional\s+)?(?:term|period)",
            r"notice\s+of\s+(?:non-)?renewal",
        ],
        category="Structure",
        severity="medium",
    ),
    ComplianceRule(
        name="Taxes",
        description="Contract should clarify who bears taxes, duties, or levies.",
        keywords=["tax", "taxes", "duties", "levies", "withholding", "tax liability"],
        patterns=[
            r"(?:each|either)\s+party\s+(?:shall\s+)?(?:be\s+responsible|bear)\s+for\s+(?:its\s+own\s+)?(?:taxes|tax)",
            r"(?:shall\s+(?:pay|bear|assume))\s+(?:all\s+)?(?:taxes|duties|levies)",
            r"(?:exclusive\s+of\s+any\s+)?(?:taxes|taxation)",
            r"(?:withholding\s+tax|tax\s+withholding)",
        ],
        category="Financial",
        severity="low",
    ),
    ComplianceRule(
        name="Binding Effect / Beneficiaries",
        description="Contract should state it binds successors/assigns and identify beneficiaries.",
        keywords=["binding", "inure", "benefit", "successors and assigns", "third party", "beneficiar"],
        patterns=[
            r"(?:binding\s+upon|shall\s+inure\s+to\s+the\s+benefit\s+of)\s+(?:the\s+)?(?:parties|heirs|successors|assigns)",
            r"successors\s+and\s+assigns",
            r"(?:no\s+)?third[-\s]party\s+beneficiar",
            r"(?:binds|binding\s+on)\s+(?:and\s+inures\s+to\s+the\s+benefit\s+of)",
        ],
        category="Structure",
        severity="medium",
    ),
]


def run_compliance_check(text: str, rules: list[ComplianceRule] = None) -> list[RuleResult]:
    """Run deterministic compliance checks against contract text using regex/keyword matching."""
    if rules is None:
        rules = DEFAULT_RULES

    text_lower = text.lower()
    results = []

    for rule in rules:
        best_match = None
        matched = False

        # Check keyword presence
        keyword_found = any(kw.lower() in text_lower for kw in rule.keywords)

        # Check regex patterns
        pattern_match = None
        for pattern in rule.patterns:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                pattern_match = m.group(0)
                break

        if keyword_found and pattern_match:
            status = "pass"
            best_match = pattern_match
            explanation = (
                f"Basis: the contract contains a matching clause - "
                f"\"{best_match[:140]}\"."
            )
        elif keyword_found:
            status = "pass"
            # Find the sentence containing the keyword for context
            sentences = re.split(r'[.!?\n]', text)
            for s in sentences:
                if any(kw.lower() in s.lower() for kw in rule.keywords):
                    best_match = s.strip()[:200]
                    break
            found_kw = next(
                (kw for kw in rule.keywords if kw.lower() in text_lower),
                "one of the key terms",
            )
            snippet = f" e.g. \"{best_match[:100]}\"" if best_match else ""
            explanation = (
                f"Basis: the contract mentions \"{found_kw}\"{snippet}."
            )
        elif pattern_match:
            status = "pass"
            best_match = pattern_match
            explanation = (
                f"Basis: clause language matched the rule's pattern - "
                f"\"{best_match[:140]}\"."
            )
        else:
            status = "missing"
            terms = " · ".join(rule.keywords[:4])
            if len(rule.keywords) > 4:
                terms += " …"
            explanation = (
                f"Basis: none of the required terms ({terms}) appear "
                f"anywhere in this document."
            )

        results.append(RuleResult(
            rule=rule,
            status=status,
            matched_text=best_match,
            explanation=explanation,
        ))

    return results


def format_checklist_markdown(results: list[RuleResult]) -> str:
    """Format compliance results as readable Markdown."""
    lines = ["# Contract Compliance Checklist\n"]

    pass_count = sum(1 for r in results if r.status == "pass")
    missing_count = sum(1 for r in results if r.status == "missing")
    total = len(results)

    lines.append(f"**{pass_count}/{total}** checks passed | **{missing_count}** clauses missing\n")

    lines.append("---\n")
    lines.append("## Results\n")

    for r in results:
        icon = {"pass": "PASS", "missing": "MISSING", "fail": "WARNING"}.get(r.status, "CHECK")
        lines.append(f"### [{icon}] {r.rule.name}")
        lines.append(f"**Category:** {r.rule.category} | **Severity:** {r.rule.severity}")
        lines.append(f"{r.explanation}")
        if r.matched_text:
            lines.append(f"\n> \"{r.matched_text}\"")
        lines.append("")

    if missing_count > 0:
        lines.append("---\n")
        lines.append("## Missing Clauses Summary\n")
        for r in results:
            if r.status == "missing":
                lines.append(f"- **{r.rule.name}** ({r.rule.severity}): {r.rule.description}")

    return "\n".join(lines)


def simplify_clauses_with_llm(text: str, llm, chunk_size: int = 6000) -> str:
    """Break contract into chunks and simplify each using the LLM."""
    import re

    # Split on clause/section boundaries
    clause_pattern = re.compile(
        r'\n\s*(?=(?:\d+\.?\s|[A-Z][A-Z\s]*\.?\s*[:\-]|SECTION|ARTICLE|CLAUSE|Section|Article|Clause))',
        re.MULTILINE
    )
    chunks = clause_pattern.split(text)
    
    # Merge small chunks to avoid too many LLM calls
    merged = []
    current = ""
    for chunk in chunks:
        if len(current) + len(chunk) < chunk_size:
            current += chunk
        else:
            if current.strip():
                merged.append(current.strip())
            current = chunk
    if current.strip():
        merged.append(current.strip())

    simplified_parts = []
    for i, chunk in enumerate(merged):
        prompt = f"""You are a legal document simplifier. Rewrite the following contract clause 
into plain, clear English that a non-lawyer can understand. Preserve all key obligations, 
deadlines, and conditions. Do NOT add legal advice or opinions. Just simplify the language.

Contract clause:
\"\"\"
{chunk}
\"\"\"

Plain English rewrite:"""

        try:
            response = llm.invoke(prompt)
            simplified_parts.append(response.content if hasattr(response, 'content') else str(response))
        except Exception as e:
            simplified_parts.append(f"[Simplification failed for chunk {i+1}: {e}]\n\n{chunk}")

    return "\n\n---\n\n".join(simplified_parts)
