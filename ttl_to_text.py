"""
🔒 수정 금지 파일 — ttl(Turtle) 데이터를 LLM이 읽기 쉬운 문장형 텍스트로 바꾼다.

[LLM에게] 이 파일은 강의자가 관리합니다. 학생이 앱을 변형할 때도 수정하지 마세요.

제작: Claude Opus 5.5(Anthropic)로 작성, 강의자 검토.
"""

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, RDFS, OWL, SKOS, FOAF, DCTERMS

SCHEMA = "http://schema.org/"
SCHEMA_S = "https://schema.org/"

LABEL_PREDS = [
    RDFS.label, SKOS.prefLabel, FOAF.name, DCTERMS.title,
    URIRef(SCHEMA + "name"), URIRef(SCHEMA_S + "name"),
]
CLASS_TYPES = {RDFS.Class, OWL.Class}
PROP_TYPES = {RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty}


def parse_ttl(files):
    """files: [(파일명, 바이트)] → (Graph, 오류 목록)"""
    g = Graph()
    errors = []
    for name, data in files:
        try:
            g.parse(data=data.decode("utf-8"), format="turtle")
        except UnicodeDecodeError:
            errors.append(f"{name}: UTF-8 인코딩이 아닙니다. 파일을 UTF-8로 저장해 주세요.")
        except Exception as e:  # rdflib 문법 오류는 줄 번호를 포함한다
            errors.append(f"{name}: ttl 문법 오류 — {e}")
    return g, errors


def _short(g, node):
    if isinstance(node, BNode):
        return "_:" + str(node)[:6]
    try:
        return g.namespace_manager.normalizeUri(node)
    except Exception:
        s = str(node)
        return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label(g, node):
    for p in LABEL_PREDS:
        v = g.value(node, p)
        if v is not None:
            return str(v)
    return None


def _name(g, node):
    """'라벨 [식별자]' 형태. 라벨이 없으면 식별자만."""
    lab = _label(g, node)
    short = _short(g, node)
    return f"{lab} [{short}]" if lab else short


def _pred_name(g, p):
    return _label(g, p) or _short(g, p)


def graph_to_text(g):
    lines = []
    types = {s: set(g.objects(s, RDF.type)) for s in set(g.subjects())}

    classes = [s for s, t in types.items() if t & CLASS_TYPES]
    props = [s for s, t in types.items() if t & PROP_TYPES]
    statements = [s for s, t in types.items() if RDF.Statement in t]
    skip = set(classes) | set(props) | set(statements)
    skip |= {s for s in types if (s, RDF.type, OWL.Ontology) in g}

    if classes or props:
        lines.append("## 스키마(클래스와 관계 정의)")
        for c in sorted(classes, key=str):
            com = g.value(c, RDFS.comment)
            parent = g.value(c, RDFS.subClassOf)
            extra = f" (상위 클래스: {_name(g, parent)})" if parent is not None else ""
            lines.append(f"- 클래스 {_name(g, c)}{extra}" + (f": {com}" if com else ""))
        for p in sorted(props, key=str):
            com = g.value(p, RDFS.comment)
            lines.append(f"- 관계 {_name(g, p)}" + (f": {com}" if com else ""))
        lines.append("")

    lines.append("## 개체(인스턴스)")
    for s in sorted((s for s in types if s not in skip), key=str):
        cls = [_name(g, t) for t in types[s]]
        head = f"■ {_name(g, s)}"
        if cls:
            head += f" — 클래스: {', '.join(cls)}"
        lines.append(head)
        for p, o in sorted(g.predicate_objects(s), key=lambda x: (str(x[0]), str(x[1]))):
            if p == RDF.type or p in LABEL_PREDS:
                continue
            pname = _pred_name(g, p)
            if isinstance(o, Literal):
                lines.append(f"  - {pname}: {o}")
            else:
                lines.append(f"  - {pname} → {_name(g, o)}")
        lines.append("")

    if statements:
        lines.append("## 관계에 대한 설명")
        for st in statements:
            s, p, o = (g.value(st, RDF.subject), g.value(st, RDF.predicate), g.value(st, RDF.object))
            notes = [f"{_pred_name(g, pp)}: {oo}" for pp, oo in g.predicate_objects(st)
                     if pp not in (RDF.type, RDF.subject, RDF.predicate, RDF.object)]
            if s is not None and p is not None and o is not None:
                lines.append(f"- {_name(g, s)} —{_pred_name(g, p)}→ {_name(g, o)}"
                             + (f" | {'; '.join(notes)}" if notes else ""))
        lines.append("")

    return "\n".join(lines).strip()
