"""Export the Bordeaux Digital Twin ontology to an OWL/Turtle file.

Reads DOMAIN_META, ONTO_RELATIONS and CAUSAL_CHAINS from app_pages/ontology.py
(the single source of truth already used by the Streamlit UI) and serializes
them as a standard OWL ontology in Turtle syntax, loadable in Protege or any
other RDF/OWL tool.

Usage:
    python ontology/export_owl.py
"""

import re
import sys
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, OWL, XSD

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app_pages.ontology import DOMAIN_META, ONTO_RELATIONS, CAUSAL_CHAINS  # noqa: E402

BTO = Namespace("http://bordeaux-twin.org/ontology#")
OUTPUT_PATH = Path(__file__).resolve().parent / "bordeaux_ontology.ttl"


def class_name(domain_label: str) -> str:
    """'Online DataSet' -> 'OnlineDataSet'"""
    return re.sub(r"[^0-9A-Za-z]", "", domain_label)


def property_name(relation_label: str) -> str:
    """'depends on' -> 'dependsOn', 'generates' -> 'generates'"""
    words = re.split(r"[\s-]+", relation_label.strip())
    return words[0] + "".join(w.capitalize() for w in words[1:])


def chain_id(title: str) -> str:
    """'Urban Traffic -> Air Pollution -> Public Health' -> 'ChainUrbanTrafficAirPollutionPublicHealth'"""
    words = re.findall(r"[0-9A-Za-z]+", title)
    return "Chain" + "".join(w.capitalize() for w in words)


def main() -> Graph:
    g = Graph()
    g.bind("bto", BTO)
    g.bind("owl", OWL)

    ontology_uri = BTO["BordeauxTwinOntology"]
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.label, Literal("Bordeaux Digital Twin Cross-Domain Ontology")))
    g.add((ontology_uri, RDFS.comment, Literal(
        "OWL ontology describing the 10 data domains of the Bordeaux Metropole "
        "digital twin, their 28 semantic relationships (with confidence level) "
        "and 6 causal chains connecting them. Generated from app_pages/ontology.py."
    )))

    # Annotation property for confidence level
    g.add((BTO.hasConfidenceLevel, RDF.type, OWL.AnnotationProperty))
    g.add((BTO.hasConfidenceLevel, RDFS.label, Literal("has confidence level")))
    g.add((BTO.hasConfidenceLevel, RDFS.comment, Literal(
        "Confidence level of a relationship: Strong, Medium or Weak."
    )))

    # --- Domains -> OWL Classes -------------------------------------------
    for domain, meta in DOMAIN_META.items():
        cls = BTO[class_name(domain)]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(domain)))

    # --- Relations -> OWL Object Properties + reified, annotated triples --
    for from_domain, relation, to_domain, strength, explanation in ONTO_RELATIONS:
        from_cls = BTO[class_name(from_domain)]
        to_cls = BTO[class_name(to_domain)]
        prop = BTO[property_name(relation)]

        # Declare the object property once (domain/range from this relation's usage)
        if (prop, RDF.type, OWL.ObjectProperty) not in g:
            g.add((prop, RDF.type, OWL.ObjectProperty))
            g.add((prop, RDFS.label, Literal(relation)))
            g.add((prop, RDFS.domain, from_cls))
            g.add((prop, RDFS.range, to_cls))

        # Direct assertion between domain classes (so SPARQL can query it directly)
        g.add((from_cls, prop, to_cls))

        # Reified statement carrying confidence level + explanation for this
        # specific relationship instance
        stmt = BNode()
        g.add((stmt, RDF.type, RDF.Statement))
        g.add((stmt, RDF.subject, from_cls))
        g.add((stmt, RDF.predicate, prop))
        g.add((stmt, RDF.object, to_cls))
        g.add((stmt, BTO.hasConfidenceLevel, Literal(strength)))
        g.add((stmt, RDFS.comment, Literal(explanation)))

    # --- Causal chains -------------------------------------------------
    g.add((BTO.CausalChain, RDF.type, OWL.Class))
    g.add((BTO.CausalChain, RDFS.label, Literal("Causal Chain")))
    g.add((BTO.CausalChain, RDFS.comment, Literal(
        "An ordered sequence of domain-level steps describing a cross-domain "
        "cause-and-effect narrative in the digital twin."
    )))

    g.add((BTO.ChainStep, RDF.type, OWL.Class))
    g.add((BTO.ChainStep, RDFS.label, Literal("Chain Step")))

    g.add((BTO.hasStep, RDF.type, OWL.ObjectProperty))
    g.add((BTO.hasStep, RDFS.label, Literal("has step")))
    g.add((BTO.hasStep, RDFS.domain, BTO.CausalChain))
    g.add((BTO.hasStep, RDFS.range, BTO.ChainStep))

    g.add((BTO.partOfCausalChain, RDF.type, OWL.ObjectProperty))
    g.add((BTO.partOfCausalChain, RDFS.label, Literal("part of causal chain")))
    g.add((BTO.partOfCausalChain, OWL.inverseOf, BTO.hasStep))
    g.add((BTO.partOfCausalChain, RDFS.domain, BTO.ChainStep))
    g.add((BTO.partOfCausalChain, RDFS.range, BTO.CausalChain))

    g.add((BTO.stepDomain, RDF.type, OWL.ObjectProperty))
    g.add((BTO.stepDomain, RDFS.label, Literal("step domain")))
    g.add((BTO.stepDomain, RDFS.domain, BTO.ChainStep))

    g.add((BTO.stepRole, RDF.type, OWL.DatatypeProperty))
    g.add((BTO.stepRole, RDFS.label, Literal("step role")))
    g.add((BTO.stepRole, RDFS.domain, BTO.ChainStep))
    g.add((BTO.stepRole, RDFS.range, XSD.string))

    g.add((BTO.stepOrder, RDF.type, OWL.DatatypeProperty))
    g.add((BTO.stepOrder, RDFS.label, Literal("step order")))
    g.add((BTO.stepOrder, RDFS.domain, BTO.ChainStep))
    g.add((BTO.stepOrder, RDFS.range, XSD.integer))

    for chain in CAUSAL_CHAINS:
        chain_uri = BTO[chain_id(chain["title"])]
        g.add((chain_uri, RDF.type, BTO.CausalChain))
        g.add((chain_uri, RDFS.label, Literal(chain["title"])))

        for i, step in enumerate(chain["steps"]):
            step_uri = BNode()
            g.add((step_uri, RDF.type, BTO.ChainStep))
            g.add((step_uri, BTO.partOfCausalChain, chain_uri))
            g.add((chain_uri, BTO.hasStep, step_uri))
            g.add((step_uri, BTO.stepDomain, BTO[class_name(step["domain"])]))
            g.add((step_uri, BTO.stepRole, Literal(step["role"])))
            g.add((step_uri, BTO.stepOrder, Literal(i, datatype=XSD.integer)))
            g.add((step_uri, RDFS.comment, Literal(step["desc"])))

    return g


if __name__ == "__main__":
    graph = main()
    graph.serialize(destination=str(OUTPUT_PATH), format="turtle")
    print(f"Wrote {len(graph)} triples to {OUTPUT_PATH}")

    # Round-trip validation: re-parse the file we just wrote
    check = Graph()
    check.parse(str(OUTPUT_PATH), format="turtle")
    print(f"Validation OK: re-parsed {len(check)} triples from {OUTPUT_PATH.name}")
