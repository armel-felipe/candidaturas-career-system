from __future__ import annotations

import hashlib
import re
import subprocess
import unicodedata
import warnings
from pathlib import Path
from typing import Any

from career.paths import CAREER_STATE, ROOT
from career.services import applications_v2 as applications_v2_service
from career.services import derived_context as derived_context_service
from career.services import fit_map as fit_map_service
from career.services.application_context import ApplicationPaths
from career.utils import (
    ValidationFailure,
    ensure,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)


PROFILE_FACTS_PATH = (
    ROOT / ".agents/skills/career-system/references/perfil_restricoes.md"
)
SELF_KNOWLEDGE_PATH = (
    ROOT / ".agents/skills/career-system/references/autoconhecimento.md"
)


CV_CONTENT_PATH = CAREER_STATE / "cv_content.json"
FIT_MAP_PATH = CAREER_STATE / "fit_map.json"


def configure_paths(*, cv_content_path: Path | None = None, fit_map_path: Path | None = None) -> None:
    warnings.warn(
        "configure_paths is a deprecated legacy adapter; pass ApplicationPaths instead",
        DeprecationWarning,
        stacklevel=2,
    )
    global CV_CONTENT_PATH
    global FIT_MAP_PATH
    if cv_content_path is not None:
        CV_CONTENT_PATH = cv_content_path
    if fit_map_path is not None:
        FIT_MAP_PATH = fit_map_path


BULLET2_POLICY_BY_FAMILY: dict[str, dict[str, Any]] = {
    "project_management": {
        "signals": {
            "projeto",
            "projetos",
            "programa",
            "implantacao",
            "implantação",
            "pm",
            "pmo",
            "rollout",
        },
        "focus": "coordenação, governança e execução transversal",
    },
    "operations": {
        "signals": {
            "operacoes",
            "operações",
            "logistica",
            "logística",
            "supply",
            "last mile",
            "fulfillment",
        },
        "focus": "ritmo operacional, indicadores e eficiência",
    },
    "planning_sop_capacity": {
        "signals": {
            "planejamento",
            "s&op",
            "capacity",
            "forecast",
            "demanda",
            "supply planning",
        },
        "focus": "cenários, capacidade e governança de planejamento",
    },
    "cx_saas_operations": {
        "signals": {
            "cx",
            "customer success",
            "customer service",
            "suporte",
            "atendimento",
            "saas",
        },
        "focus": "jornada, automação e integração de atendimento",
    },
    "product_revenue_business_ops": {
        "signals": {
            "product",
            "produto",
            "revenue",
            "growth",
            "pricing",
            "business ops",
        },
        "focus": "dados, priorização e performance de negócio",
    },
}


EXPERIENCE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "wehandle_head_operacoes",
        "company": "wehandle",
        "role": "Head de Operações",
        "period": "maio/2024 — fev/2026",
        "order": 1,
        "focus_terms": {"transformação digital", "inteligência artificial", "liderança", "dados", "cx"},
        "scope_bullet": "Fui responsável pela operação de suporte, CX e backoffice, liderando um time de 30 pessoas e conectando atendimento, produto e dados para acelerar a transformação digital da companhia.",
        "result_bullet": "Reduzi o custo por atendimento de R$4,14 para R$3,61 (-13%), elevei o CSAT de 85% para 92%, reduzi o TME de 20 para 8 minutos e gerei impacto de 15% na margem bruta.",
        "leverage": {
            "default": "Implantei duas migrações de plataforma, automação com inteligência artificial humanizada e integração de dados via API para dar escala operacional e melhorar a priorização com o time de produto.",
            "project_management": "Coordenei duas migrações de plataforma, organizei dependências entre atendimento, produto e tecnologia e usei integrações via API para sustentar rollout operacional com governança e visibilidade em tempo real.",
            "cx_saas_operations": "Estruturei migrações de plataforma, automação com inteligência artificial humanizada e integrações via API para redesenhar a jornada de atendimento e dar escala ao backoffice com melhor priorização.",
        },
    },
    {
        "id": "ifood_diretor_operacoes",
        "company": "iFood",
        "role": "Diretor de Operações",
        "period": "abr/2022 — mar/2024",
        "order": 2,
        "focus_terms": {"growth", "liderança", "planejamento estratégico", "budget", "canais", "pipeline"},
        "scope_bullet": "Fui responsável por FieldOps, Meios de Pagamento e Novos Negócios, liderando 240 pessoas entre diretos e indiretos e operando growth com expansão geográfica, frota dedicada e alocação de budget.",
        "result_bullet": "Ampliei a cobertura logística de 400 para 800 cidades, reduzi a indisponibilidade da frota de 5% para 1%, aumentei viagens agrupadas de 12% para 25% e gerenciei budget de R$300MM/ano.",
        "leverage": {
            "default": "Conectei marketing, produto, supply e operação em um rito executivo mensal de S&OP, conduzindo cenários, trade-offs e governança para sustentar decisões de crescimento e eficiência.",
            "project_management": "Coordenei marketing, produto, supply e operação em um rito executivo mensal de S&OP, desdobrando cenários, riscos e dependências para sustentar decisões transversais de crescimento com governança.",
            "planning_sop_capacity": "Conduzi um rito executivo mensal de S&OP com marketing, produto, supply e operação, usando cenários, trade-offs e governança para balancear capacidade, custo e nível de serviço.",
        },
    },
    {
        "id": "ifood_head_operacoes",
        "company": "iFood",
        "role": "Head de Operações",
        "period": "nov/2018 — mar/2022",
        "order": 3,
        "focus_terms": {"dashboards", "pricing", "data-driven growth", "growth", "dados"},
        "scope_bullet": "Fui responsável por liveOps, regionalOps, pricing, modelagem de dados e planejamento de frota, liderando 28 pessoas em uma operação que exigia decisões rápidas e coordenação multifuncional.",
        "result_bullet": "Gerei saving de R$70MM/ano com um simulador de nível de serviço, reduzi o custo de distribuição de MPOS em 80%, cortei o prazo de entrega de 14 para 2 dias e reduzi cancelamentos em 60% no México.",
        "leverage": {
            "default": "Estruturei dashboards em Grafana, modelei dados com SQL, Databricks e Tableau e conduzi testes controlados de pricing e incentivos para equilibrar oferta, demanda e nível de serviço.",
            "project_management": "Estruturei dashboards em Grafana, modelei dados com SQL e conduzi testes controlados de pricing para alinhar produto, operação e planejamento em decisões rápidas com visibilidade executiva.",
            "product_revenue_business_ops": "Modelei dados com SQL, Databricks e Tableau, criei dashboards em Grafana e conduzi testes controlados de pricing para equilibrar oferta, demanda e performance de negócio.",
        },
    },
    {
        "id": "renault_cs",
        "company": "Renault do Brasil",
        "role": "Gerente de Customer Success",
        "period": "jan/2018 — out/2018",
        "order": 4,
        "focus_terms": {"pipeline", "taxa de conversão", "conversão", "leads"},
        "scope_bullet": "Fui responsável pela transição de dois BPOs com 40 PAs para uma estrutura internalizada de 8 pessoas, redesenhando a operação de leads com mais controle de qualidade e SLA.",
        "result_bullet": "Elevei a taxa de conversão de leads de 24% para 46% e aprovei o projeto de transformação em 2 reuniões com base em um ROI corretamente modelado.",
        "leverage": {
            "default": "Estruturei governança de funil com dados, discadores programados por mim e acompanhamento em tempo real para estabilizar a execução comercial.",
            "project_management": "Estruturei a transição com governança de funil, acompanhamento em tempo real e cadência de decisão baseada em ROI para estabilizar a execução comercial sem perder SLA.",
        },
    },
    {
        "id": "vivareal_planejamento_operacoes",
        "company": "VivaReal",
        "role": "Gerente de Planejamento Comercial e Operações",
        "period": "mai/2015 — dez/2017",
        "order": 5,
        "focus_terms": {"desenvolvimento de negócios", "canais de vendas", "política de preços", "pipeline", "taxa de conversão", "liderança"},
        "scope_bullet": "Fui responsável por planejamento comercial, desenvolvimento de negócios, canais de vendas, política de preços e operações ligadas a SDR, qualidade e cadastro de imóveis, totalizando 33 pessoas e 5 lideranças diretas.",
        "result_bullet": "Elevei a taxa de conversão de SDR inbound de 18% para 50%, reduzi o custo de vendas em 40%, recuperei R$1M em campanhas de inadimplência e escalei a área desenhada de CS para 91 pessoas.",
        "leverage": {
            "default": "Estruturei dashboards diários com SQL e Excel automatizado, organizei o pipeline de SDR, defini metas com o time comercial e priorizei roadmap de produto para sustentar expansão e execução.",
            "project_management": "Coordenei SQL, Excel automatizado, pipeline de SDR e priorização de roadmap de produto para alinhar stakeholders, destravar dependências e sustentar a execução do plano comercial.",
            "product_revenue_business_ops": "Estruturei dashboards diários com SQL, automatizei análises em Excel, organizei o pipeline de SDR e priorizei roadmap de produto para sustentar expansão e performance comercial.",
        },
    },
    {
        "id": "trifil_sop",
        "company": "Scalina (Trifil)",
        "role": "Coordenador de S&OP",
        "period": "jan/2010 — set/2014",
        "order": 6,
        "focus_terms": {"s&op", "planejamento integrado", "trade-offs", "cenários", "custos", "otif"},
        "scope_bullet": "Fui responsável por criar a área de S&OP do zero, gerenciando 40K SKUs de produto acabado em duas marcas e todos os canais de distribuição com responsabilidade sobre OTIF, fill rate e estoque de segurança.",
        "result_bullet": "Reduzi R$8MM em Gastos Gerais de Fabricação (GGF) via otimização de energia, gás, manutenção e embalagens, mantendo a meta anual de R$154M com economia real de R$4,6M até agosto.",
        "leverage": {
            "default": "Desenvolvi um simulador para validação do MRP e avaliação de cenários no S&OP com Excel/VBA, coordenei o S&OE para recalibrar faltas e sobras e atuei como intermediador entre comercial e fabricação para resolver restrições de recursos.",
            "planning_sop_capacity": "Conduzi um simulador para validação do MRP e cenários de S&OP com Excel/VBA, coordenei o S&OE e articulei trade-offs entre comercial e fabricação para balancear capacidade, estoque e nível de serviço.",
            "operations": "Estruturei um simulador para validação do MRP, coordenei o S&OP e S&OE com governança de alinhamento entre comercial e fabricação para resolver restrições operacionais e sustentar OTIF, fill rate e estoque de segurança.",
        },
    },
    {
        "id": "trifil_inteligencia_comercial",
        "company": "Scalina (Trifil)",
        "role": "Coordenador de Inteligência Comercial",
        "period": "jan/2009 — dez/2009",
        "order": 7,
        "focus_terms": {"data-driven growth", "dashboards", "insights", "pricing", "canais de vendas"},
        "scope_bullet": "Fui responsável por criar a área de inteligência comercial, apoiando a diretoria com informações de mercado, canais de vendas, comissionamento, oportunidades comerciais e política de preços.",
        "result_bullet": "Reduzi o tempo dos relatórios diários de 4 horas para 14 minutos e aumentei o faturamento anual de R$80M para R$120M com um algoritmo de alocação de estoque orientado por margem e receita.",
        "leverage": {
            "default": "Estruturei análises com dados, BI, dashboards e rotinas em Excel/VBA para sustentar decisões comerciais, normalizar dados do ERP e preparar a base para o sistema B2B.",
            "project_management": "Estruturei análises com BI, dashboards e rotinas em Excel/VBA, organizei a base do ERP e dei previsibilidade à diretoria para priorizar decisões comerciais e implantação do sistema B2B.",
            "product_revenue_business_ops": "Estruturei análises com BI, dashboards e rotinas em Excel/VBA, normalizei dados do ERP e preparei a base para decisões comerciais orientadas por margem, receita e canais.",
        },
    },
]


DEFAULT_EDUCATION_PT = [
    "MBA Corporate Strategy — BSP Business School São Paulo (2017)",
    "Engenheiro Químico — Faculdades Oswaldo Cruz (2014)",
    "Six Sigma Green Belt — Setec Consulting (2020)",
]

DEFAULT_EDUCATION_EN = [
    "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo (2017)",
    "Bachelor's Degree in Chemical Engineering — Faculdades Oswaldo Cruz (2014)",
    "Six Sigma Green Belt — Setec Consulting (2020)",
]

DEFAULT_LANGUAGES = [
    "Português — Nativo",
    "Inglês — Avançado",
]

DEFAULT_LANGUAGES_EN = [
    "Portuguese — Native",
    "English — Advanced",
]

DEFAULT_STACK = "Excel/VBA · SQL · Python · Databricks · Grafana · Tableau · Power BI · Metabase"

EN_EXPERIENCE_TEXT = {
    "wehandle_head_operacoes": ("Head of Operations", "I led Support, CX, and Back Office, managing a 30-person team and connecting service, product, and data to accelerate the company's digital transformation.", "I implemented two platform migrations, human-centered AI automation, and API data integrations to scale operations and improve product prioritization.", "I reduced cost per contact from R$4.14 to R$3.61 (-13%), raised CSAT from 85% to 92%, cut handling time from 20 to 8 minutes, and generated a 15% gross-margin impact."),
    "ifood_diretor_operacoes": ("Operations Director", "I led FieldOps, Payments, and New Business, managing 240 direct and indirect people across geographic expansion, dedicated fleet, and budget allocation.", "I connected marketing, product, supply, and operations through a monthly executive S&OP cadence, using scenarios and trade-offs to support growth and efficiency decisions.", "I expanded logistics coverage from 400 to 800 cities, reduced fleet unavailability from 5% to 1%, increased bundled trips from 12% to 25%, and managed an annual R$300M budget."),
    "ifood_head_operacoes": ("Head of Operations", "I led live operations, regional operations, pricing, data modeling, and fleet planning with a 28-person team in a fast-paced cross-functional environment.", "I built Grafana dashboards, modeled data with SQL, Databricks, and Tableau, and ran controlled pricing and incentive experiments to balance supply, demand, and service levels.", "I generated R$70M in annual savings with a service-level simulator, cut MPOS distribution cost by 80%, reduced delivery time from 14 to 2 days, and lowered cancellations in Mexico by 60%."),
    "renault_cs": ("Customer Success Manager", "I transitioned two BPO operations with 40 workstations to an in-house eight-person team, redesigning lead operations for stronger quality control and SLA management.", "I established funnel governance with data, self-configured dialers, and real-time monitoring to stabilize commercial execution.", "I increased lead conversion from 24% to 46% and obtained approval for the transformation project in two meetings through a correctly modeled ROI."),
    "vivareal_planejamento_operacoes": ("Commercial Planning and Operations Manager", "I led commercial planning, business development, sales channels, pricing policy, and SDR, quality, and real-estate listing operations, totaling 33 people and five direct leaders.", "I built daily SQL and automated Excel dashboards, organized the SDR pipeline, set sales goals, and prioritized the product roadmap to sustain execution and growth.", "I increased inbound SDR conversion from 18% to 50%, reduced sales cost by 40%, recovered R$1M from delinquency campaigns, and scaled the designed CS area to 91 people."),
    "trifil_sop": ("S&OP Coordinator", "I created the S&OP function from scratch, managing 40K finished-goods SKUs across two brands and all distribution channels, with accountability for OTIF, fill rate, and safety stock.", "I developed an Excel/VBA simulator to validate MRP and evaluate S&OP scenarios, coordinated S&OE, and mediated constraints between commercial and manufacturing teams.", "I reduced R$8M in manufacturing overhead through energy, gas, maintenance, and packaging optimization while maintaining the R$154M annual target and delivering R$4.6M in realized savings by August."),
    "trifil_inteligencia_comercial": ("Commercial Intelligence Coordinator", "I created the commercial intelligence function, supporting executive leadership with market information, sales channels, commissions, commercial opportunities, and pricing policy.", "I built data analyses, BI dashboards, and Excel/VBA routines to support commercial decisions, normalize ERP data, and prepare the foundation for the B2B system.", "I reduced daily reporting time from four hours to 14 minutes and increased annual revenue from R$80M to R$120M through a margin- and revenue-based inventory-allocation algorithm."),
}


def build_current_cv_content(path: Path = CV_CONTENT_PATH) -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    _ensure_fit_map_matches_active(active)
    fit_map = read_json(FIT_MAP_PATH)
    payload = _build_cv_payload(active, fit_map, source_fit_map=str(FIT_MAP_PATH))
    write_json(path, payload)
    validate_cv_content(path)
    return payload


def build_cv_content(
    application_paths: ApplicationPaths,
    fit_map_path: Path,
    candidate_facts_revision: str,
) -> dict[str, Any]:
    """Build CV content from explicit application paths without global adapters."""
    resolved_fit_map = Path(fit_map_path).resolve()
    for label, path in (
        ("job description", application_paths.job_description.resolve()),
        ("FIT_MAP", resolved_fit_map),
        ("CV content", application_paths.cv_content.resolve()),
    ):
        try:
            path.relative_to(application_paths.app_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"{label} must stay within its application directory") from exc
    ensure(application_paths.job_description.is_file(), "application_job_description_missing")
    ensure(resolved_fit_map.is_file(), "application_fit_map_missing")
    identity = read_json(application_paths.identity) if application_paths.identity.is_file() else {}
    active = derived_context_service.ActiveJobContext(
        job_description_path=application_paths.job_description.resolve(),
        fingerprint=sha256_file(application_paths.job_description),
        company=str(identity.get("company") or ""),
        role=str(identity.get("role") or ""),
        source_type=str(identity.get("source_type") or "application_source"),
        source_id=str(identity.get("source_id") or "") or None,
    )
    fit_map = read_json(resolved_fit_map)
    fit_map_service.validate_application_fit_map(
        fit_map,
        application_paths=application_paths,
        expected_candidate_facts_revision=candidate_facts_revision,
    )
    payload = _build_cv_payload(
        active,
        fit_map,
        source_fit_map=str(resolved_fit_map),
        candidate_facts_revision=candidate_facts_revision,
        application_id=application_paths.application_id,
        language=_application_cv_language(application_paths, fit_map),
    )
    return payload


def render_cv(content_path: Path, output_dir: Path, application_id: str) -> Path:
    """Render one immutable application CV without consulting global state."""
    content_path = Path(content_path).resolve()
    output_dir = Path(output_dir).resolve()
    if not content_path.is_file():
        raise ValueError("cv_content_missing")
    payload = read_json(content_path)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if metadata.get("application_id") != application_id:
        raise ValueError("cv_content_application_id_mismatch")
    output_name = str(payload.get("output_name") or "").strip()
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("cv_content_output_name_invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "node",
        "scripts/docx/generate_custom_cv.js",
        "--content",
        str(content_path),
        "--output-dir",
        str(output_dir),
        "--application-id",
        application_id,
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            "cv_renderer_failed:\n"
            f"stdout={result.stdout}\n"
            f"stderr={result.stderr}"
        )
    artifact = output_dir / output_name
    if not artifact.is_file():
        raise RuntimeError("cv_renderer_did_not_create_artifact")
    return artifact


def _build_cv_payload(
    active: derived_context_service.ActiveJobContext,
    fit_map: dict[str, Any],
    *,
    source_fit_map: str,
    candidate_facts_revision: str | None = None,
    application_id: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    job_family = _infer_job_family(fit_map)
    selected = _select_experiences(fit_map)
    ensure(4 <= len(selected) <= 8, "cv_content_requires_between_4_and_8_experiences")
    is_en = (language or _cv_language(fit_map)) == "en"
    selected_with_bullets = [_materialize_experience(entry, job_family, language="en" if is_en else "pt-BR") for entry in selected]
    top8 = _top8_keywords(fit_map)
    coverage = _build_ats_coverage(selected_with_bullets, top8)
    summary_text, summary_support = _build_summary(selected_with_bullets, fit_map, language="en" if is_en else "pt-BR")
    education_list = DEFAULT_EDUCATION_EN if is_en else DEFAULT_EDUCATION_PT
    candidate = _candidate_contact_facts()
    payload = {
        "metadata": {
            "kind": "cv_content",
            "created_at": utc_now_iso(),
            "job_fingerprint": active.fingerprint,
            "job_description_path": derived_context_service._relative(active.job_description_path),
            "candidate_facts_revision": candidate_facts_revision,
            "application_id": application_id,
            "cargo": fit_map.get("cargo"),
            "empresa": fit_map.get("empresa"),
            "source_fit_map": source_fit_map,
            "job_family": job_family,
            "language": "en" if is_en else "pt-BR",
        },
        "output_name": _output_name(fit_map, active=active, language="en" if is_en else "pt-BR"),
        "candidate": candidate,
        "mode": "concise",
        "persona": _persona_name(fit_map),
        "summary": summary_text,
        "resumo": summary_text,
        "experiences": [
            {
                "experience_id": exp["id"],
                "evidence_id": _evidence_id(exp["id"], "experience"),
                "role": exp["role"],
                "company": exp["company"],
                "period": exp["period"],
                "bullets": [
                    {
                        "text": bullet,
                        "experience_id": exp["id"],
                        "evidence_id": _evidence_id(exp["id"], f"bullet:{index}"),
                    }
                    for index, bullet in enumerate(exp["bullets"])
                ],
            }
            for exp in selected_with_bullets
        ],
        "experiencias": [
            {
                "experience_id": exp["id"],
                "evidence_id": _evidence_id(exp["id"], "experience"),
                "cargo": exp["role"],
                "empresa": exp["company"],
                "periodo": exp["period"],
                "bullets": [bullet for bullet in exp["bullets"]],
            }
            for exp in selected_with_bullets
        ],
        "education": list(education_list),
        "formacao": list(DEFAULT_EDUCATION_PT),
        "languages": list(DEFAULT_LANGUAGES_EN if is_en else DEFAULT_LANGUAGES),
        "idiomas": list(DEFAULT_LANGUAGES),
        "stack": DEFAULT_STACK,
        "ats_keyword_coverage": coverage,
        "summary_support": summary_support,
    }
    _attach_canonical_provenance(payload)
    return payload


def validate_cv_content(path: Path = CV_CONTENT_PATH) -> dict[str, Any]:
    ensure(path.exists(), f"cv_content_missing: {path}")
    active = derived_context_service.resolve_active_job_context()
    payload = read_json(path)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    ensure(metadata.get("job_fingerprint") == active.fingerprint, "cv_content_stale_for_active_job")
    ensure(str(metadata.get("cargo") or "").strip(), "cv_content_missing_cargo_metadata")
    ensure(str(metadata.get("empresa") or "").strip(), "cv_content_missing_empresa_metadata")
    mock_paths = {
        "cv_content": path,
        "fit_map": FIT_MAP_PATH,
    }
    applications_v2_service._validate_cv_content_contract(mock_paths)
    return {
        "status": "ok",
        "path": str(path),
        "job_fingerprint": metadata.get("job_fingerprint"),
        "output_name": payload.get("output_name"),
        "experiences_count": len(payload.get("experiences", []) or []),
    }


def active_artifact_status() -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    fit_map_status = fit_map_service.status()
    cv_status = {
        "exists": CV_CONTENT_PATH.exists(),
        "path": str(CV_CONTENT_PATH),
        "matches_active_job": False,
    }
    if CV_CONTENT_PATH.exists():
        payload = read_json(CV_CONTENT_PATH)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        cv_status["matches_active_job"] = metadata.get("job_fingerprint") == active.fingerprint
        cv_status["output_name"] = payload.get("output_name")
    return {
        "status": "ok" if fit_map_status.get("fit_map", {}).get("matches_active_job") and cv_status["matches_active_job"] else "blocked",
        "active_job": {
            "path": derived_context_service._relative(active.job_description_path),
            "fingerprint": active.fingerprint,
        },
        "fit_map": fit_map_status.get("fit_map", {}),
        "cv_content": cv_status,
    }


def invalidate_stale_artifacts() -> dict[str, Any]:
    active = derived_context_service.resolve_active_job_context()
    invalidated: list[str] = []
    for path in (CV_CONTENT_PATH,):
        if not path.exists():
            continue
        payload = read_json(path)
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if metadata.get("job_fingerprint") != active.fingerprint:
            stale_path = path.with_suffix(path.suffix + ".stale")
            path.rename(stale_path)
            invalidated.append(str(stale_path))
    return {
        "status": "ok",
        "active_fingerprint": active.fingerprint,
        "invalidated": invalidated,
    }


def _ensure_fit_map_matches_active(active: Any) -> None:
    status = fit_map_service.status(fit_map_path=FIT_MAP_PATH, job_description_path=active.job_description_path)
    ensure(status.get("fit_map", {}).get("matches_active_job"), "fit_map_stale_for_active_job")


def _top8_keywords(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [item for item in fit_map.get("keywords_habilidade_ats", []) if isinstance(item, dict)]
    entries.sort(key=lambda item: int(item.get("prioridade") or 999))
    return entries[:8]


def _select_experiences(fit_map: dict[str, Any]) -> list[dict[str, Any]]:
    selected_ids: list[str] = []
    story_companies = []
    stories = fit_map.get("historias_selecionadas", {}) if isinstance(fit_map.get("historias_selecionadas"), dict) else {}
    for key in ("principal", "secundaria", "terceira"):
        story = stories.get(key)
        if isinstance(story, dict):
            story_companies.append(str(story.get("empresa") or ""))
    targets = [str(item.get("experiencia_alvo") or "") for item in _top8_keywords(fit_map)]
    for entry in EXPERIENCE_CATALOG:
        company_norm = _normalize(entry["company"])
        role_norm = _normalize(entry["role"])
        if any(company_norm in _normalize(company) for company in story_companies if company):
            selected_ids.append(entry["id"])
            continue
        if any(company_norm in _normalize(target) or role_norm in _normalize(target) for target in targets):
            selected_ids.append(entry["id"])
    fallback_priority = [
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "vivareal_planejamento_operacoes",
        "trifil_sop",
        "trifil_inteligencia_comercial",
        "wehandle_head_operacoes",
        "renault_cs",
    ]
    for item_id in fallback_priority:
        if item_id not in selected_ids:
            selected_ids.append(item_id)
        if len(selected_ids) >= 5:
            break
    deduped = [item for item in EXPERIENCE_CATALOG if item["id"] in selected_ids]
    deduped.sort(key=lambda item: item["order"])
    return deduped[:8]


def _build_ats_coverage(selected: list[dict[str, Any]], top8: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for keyword_entry in top8:
        keyword = str(keyword_entry.get("keyword") or "").strip()
        target = _normalize(str(keyword_entry.get("experiencia_alvo") or ""))
        match_index = 0
        bullet_index = 0
        for index, experience in enumerate(selected):
            if _normalize(experience["company"]) in target or _normalize(experience["role"]) in target:
                match_index = index
                break
        bullet_index = _best_bullet_index(selected[match_index]["bullets"], keyword)
        coverage.append(
            {
                "keyword": keyword,
                "experience_index": match_index,
                "experience_id": selected[match_index]["id"],
                "evidence_id": _evidence_id(
                    selected[match_index]["id"], f"bullet:{bullet_index}"
                ),
                "experience_role": selected[match_index]["role"],
                "bullet_index": bullet_index,
                "coverage_mode": "exact",
                "defensible_evidence": selected[match_index]["bullets"][bullet_index],
            }
        )
    return coverage


def _infer_job_family(fit_map: dict[str, Any]) -> str:
    tokens: list[str] = []
    for field in ("cargo", "empresa", "dor_central"):
        value = fit_map.get(field)
        if isinstance(value, str):
            tokens.append(value)
    for item in fit_map.get("keywords_habilidade_ats", []):
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        if keyword:
            tokens.append(keyword)
    haystack = " ".join(_normalize(token) for token in tokens)
    for family, payload in BULLET2_POLICY_BY_FAMILY.items():
        for signal in payload["signals"]:
            if _normalize(signal) in haystack:
                return family
    return "operations"


def _materialize_experience(entry: dict[str, Any], job_family: str, *, language: str = "pt-BR") -> dict[str, Any]:
    if language == "en":
        role, scope, leverage, result = EN_EXPERIENCE_TEXT[entry["id"]]
        return {
            **entry,
            "role": role,
            "period": _english_period(str(entry["period"])),
            "scope_bullet": scope,
            "result_bullet": result,
            "bullets": [scope, leverage, result],
            "job_family": job_family,
        }
    leverage = entry.get("leverage") if isinstance(entry.get("leverage"), dict) else {}
    bullet2 = str(leverage.get(job_family) or leverage.get("default") or "").strip()
    bullets = [
        str(entry.get("scope_bullet") or "").strip(),
        bullet2,
        str(entry.get("result_bullet") or "").strip(),
    ]
    return {
        **entry,
        "bullets": bullets,
        "job_family": job_family,
    }


def _best_bullet_index(bullets: list[str], keyword: str) -> int:
    keyword_norm = _normalize(keyword)
    for index, bullet in enumerate(bullets):
        if keyword_norm in _normalize(bullet):
            return index
    return 0


def _build_summary(selected: list[dict[str, Any]], fit_map: dict[str, Any], *, language: str = "pt-BR") -> tuple[str, list[dict[str, Any]]]:
    cargo = str(fit_map.get("cargo") or "a vaga")
    support_pairs = _summary_support_pairs(selected, language=language)
    supports = [
        {
            "summary_fragment": fragment,
            "experience_index": exp_index,
            "experience_id": selected[exp_index]["id"],
            "evidence_id": _evidence_id(
                selected[exp_index]["id"], f"bullet:{bullet_index}"
            ),
            "experience_role": selected[exp_index]["role"],
            "experience_company": selected[exp_index]["company"],
            "bullet_index": bullet_index,
            "defensible_evidence": selected[exp_index]["bullets"][bullet_index],
        }
        for fragment, exp_index, bullet_index in support_pairs
    ]
    if language == "en":
        opening = "Operations executive with 20+ years of experience in operations, commercial planning, and business intelligence."
        summary = f"{opening} I have delivered {supports[0]['summary_fragment']}. I also led initiatives that generated {supports[1]['summary_fragment']}. I am pursuing a {cargo} role connecting channels, pricing, data, and execution."
        return summary, supports
    opening = _summary_opening(fit_map)
    summary = (
        f"{opening} "
        f"Na trajetória recente, entreguei {supports[0]['summary_fragment']}. "
        f"Também liderei frentes que geraram {supports[1]['summary_fragment']}. "
        f"Busco posição de {cargo} conectando canais, pricing, dados e execução."
    )
    return summary, supports


def _summary_opening(fit_map: dict[str, Any]) -> str:
    text_parts = [
        str(fit_map.get("cargo") or ""),
        str(fit_map.get("empresa") or ""),
        str(fit_map.get("dor_central") or ""),
    ]
    for field in ("keywords_vaga", "competencias_vaga"):
        values = fit_map.get(field) or []
        if isinstance(values, list):
            text_parts.extend(str(item) for item in values)
    normalized = _normalize(" ".join(part for part in text_parts if part))
    engineering_signals = {
        "engenharia",
        "engineer",
        "industrial",
        "industria",
        "manufatura",
        "manufacturing",
        "producao",
        "produção",
        "qualidade",
        "quality",
        "regulatorio",
        "regulatório",
        "farmaceut",
        "pharma",
        "plant",
        "lean",
        "six sigma",
    }
    if any(_normalize(signal) in normalized for signal in engineering_signals):
        return (
            "Executivo com formação em Engenharia Química e MBA Corporate Strategy, "
            "com mais de 20 anos em operações, planejamento comercial e inteligência de negócios."
        )
    return "Executivo com mais de 20 anos em operações, planejamento comercial e inteligência de negócios."


def _summary_support_pairs(selected: list[dict[str, Any]], *, language: str = "pt-BR") -> list[tuple[str, int, int]]:
    desired = [
        "wehandle_head_operacoes",
        "ifood_diretor_operacoes",
        "ifood_head_operacoes",
        "trifil_sop",
        "vivareal_planejamento_operacoes",
        "trifil_inteligencia_comercial",
        "renault_cs",
    ]
    summary_fragments = {
        "wehandle_head_operacoes": ("redução de 13% no custo por atendimento e impacto de 15% na margem bruta", 2),
        "ifood_diretor_operacoes": ("400 para 800 cidades e budget logístico de R$300MM/ano", 2),
        "ifood_head_operacoes": ("R$70MM/ano em economia e redução de 60% dos cancelamentos no México", 2),
        "trifil_sop": ("40K SKUs sob governança de S&OP e R$8MM de redução de GGF", 2),
        "vivareal_planejamento_operacoes": ("conversão de SDR inbound de 18% para 50% e redução de 40% no custo de vendas", 2),
        "trifil_inteligencia_comercial": ("faturamento anual de R$80M para R$120M com algoritmo de alocação de estoque", 2),
        "renault_cs": ("conversão de leads de 24% para 46% com operação internalizada", 2),
    }
    if language == "en":
        summary_fragments = {
            "wehandle_head_operacoes": ("a 13% reduction in cost per contact and a 15% gross-margin impact", 2),
            "ifood_diretor_operacoes": ("expansion from 400 to 800 cities and management of an annual R$300M budget", 2),
            "ifood_head_operacoes": ("R$70M in annual savings and a 60% reduction in cancellations in Mexico", 2),
            "trifil_sop": ("40K SKUs under S&OP governance and an R$8M overhead reduction", 2),
            "vivareal_planejamento_operacoes": ("inbound SDR conversion from 18% to 50% and a 40% sales-cost reduction", 2),
            "trifil_inteligencia_comercial": ("annual revenue growth from R$80M to R$120M through an inventory-allocation algorithm", 2),
            "renault_cs": ("lead conversion growth from 24% to 46% through an in-house operation", 2),
        }
    by_id = {entry["id"]: index for index, entry in enumerate(selected)}
    pairs: list[tuple[str, int, int]] = []
    for experience_id in desired:
        if experience_id not in by_id:
            continue
        fragment, bullet_index = summary_fragments[experience_id]
        pairs.append((fragment, by_id[experience_id], bullet_index))
        if len(pairs) == 2:
            break
    ensure(len(pairs) >= 2, "cv_summary_requires_two_supported_experiences")
    return pairs


def _persona_name(fit_map: dict[str, Any]) -> str:
    cargo = _normalize(str(fit_map.get("cargo") or ""))
    if "growth" in cargo or "negocio" in cargo:
        return "growth_operacional"
    return "operacoes_planejamento"


def _output_name(
    fit_map: dict[str, Any], *, active: Any | None = None, language: str | None = None
) -> str:
    # Keep the artifact name stable across reruns by preferring the original
    # intake identity instead of translated/adapted labels inside the FIT_MAP.
    cargo_source = str(getattr(active, "role", "") or fit_map.get("cargo") or "vaga")
    empresa_source = str(getattr(active, "company", "") or fit_map.get("empresa") or "empresa")
    cargo = _slug(cargo_source)
    empresa = _slug(empresa_source)
    suffix = "_en" if (language or _cv_language(fit_map)) == "en" else ""
    return f"felipe_armel_cv_{cargo}_{empresa}{suffix}.docx"


def _cv_language(fit_map: dict[str, Any]) -> str:
    return "en" if str(fit_map.get("idioma") or "").strip().casefold().startswith("en") else "pt-BR"


def _application_cv_language(application_paths: ApplicationPaths, fit_map: dict[str, Any]) -> str:
    """Read the persisted normalized language; never infer it from marker words here."""
    for key in ("required_cv_language", "idioma", "language"):
        language = str(fit_map.get(key) or "").strip()
        if language in {"pt-BR", "en"}:
            return language
    extract_path = application_paths.derived_dir / "job_extract.json"
    if extract_path.is_file():
        extract = read_json(extract_path)
        language = str((extract.get("job_identity") or {}).get("language") or "").strip()
        if language in {"pt-BR", "en"}:
            return language
    raise ValidationFailure("application CV language is missing from normalized inputs")


def _candidate_contact_facts() -> dict[str, str]:
    """Extract immutable renderer-facing identity facts from the canonical profile."""
    text = PROFILE_FACTS_PATH.read_text(encoding="utf-8")
    patterns = {
        "location": r"\*\*Localização:\*\*\s*(.+)",
        "linkedin": r"\*\*LinkedIn:\*\*\s*\[([^]]+)\]",
        "phone": r"\*\*(?:WhatsApp/Tel|Telefone):\*\*\s*\[([^]]+)\]",
        "email": r"\*\*E-mail:\*\*\s*\[([^]]+)\]",
    }
    values = {
        key: (match.group(1).strip() if (match := re.search(pattern, text)) else "")
        for key, pattern in patterns.items()
    }
    name_match = re.search(r"##\s+PERFIL\s+—\s+(.+)", text, flags=re.IGNORECASE)
    values["name"] = (
        name_match.group(1).title().replace(" Da ", " da ") if name_match else ""
    )
    if not all(values.values()):
        raise ValidationFailure("canonical candidate contact facts are incomplete")
    return values


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _slug(text: str) -> str:
    slug = _normalize(text)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "arquivo"


def _evidence_id(experience_id: str, claim: str) -> str:
    """Legacy placeholder replaced by canonical binding during payload assembly."""
    return f"unbound:{experience_id}:{claim}"


def _attach_canonical_provenance(payload: dict[str, Any]) -> None:
    """Bind every renderer-facing fact to immutable candidate source hashes."""
    revision = str(payload["metadata"].get("candidate_facts_revision") or "")
    sources = {
        "profile": PROFILE_FACTS_PATH,
        "self_knowledge": SELF_KNOWLEDGE_PATH,
    }
    catalog = {
        name: {"path": str(path), "sha256": sha256_file(path)}
        for name, path in sources.items()
    }
    source_text = {
        name: _normalize(path.read_text(encoding="utf-8"))
        for name, path in sources.items()
    }

    def value_hash(value: Any) -> str:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

    def evidence_id(source: str, kind: str, locator: str, value: Any) -> str:
        return hashlib.sha256(
            f"{revision}\0{source}\0{kind}\0{locator}\0{value_hash(value)}".encode("utf-8")
        ).hexdigest()

    evidence: dict[str, dict[str, str]] = {}

    def bind(source: str, kind: str, locator: str, value: Any) -> str:
        # A claim can only be published when its locator resolves in the
        # revision-pinned canonical source.  The opaque ID protects callers
        # from treating labels as proof while preserving auditability.
        if _normalize(locator.split("::", 1)[0]) not in source_text[source]:
            raise ValidationFailure(f"canonical evidence locator is absent: {source}/{kind}")
        item_id = evidence_id(source, kind, locator, value)
        evidence[item_id] = {
            "source": source,
            "kind": kind,
            "locator": locator,
            "value_sha256": value_hash(value),
        }
        return item_id

    for experience in payload["experiences"]:
        experience_id = str(experience["experience_id"])
        locator = _experience_source_locator(experience_id)
        experience["evidence_id"] = bind("self_knowledge", "experience", locator, experience_id)
        experience["provenance"] = {
            "role": bind("self_knowledge", "experience_role", locator, experience["role"]),
            "company": bind("self_knowledge", "experience_company", locator, experience["company"]),
            "period": bind("self_knowledge", "experience_period", locator, experience["period"]),
        }
        for index, bullet in enumerate(experience["bullets"]):
            bullet["evidence_id"] = bind(
                "self_knowledge", "experience_bullet", f"{locator}::{index}", bullet["text"]
            )
    for experience in payload["experiencias"]:
        experience_id = str(experience["experience_id"])
        locator = _experience_source_locator(experience_id)
        experience["evidence_id"] = bind("self_knowledge", "experience_pt", locator, experience_id)
        experience["provenance"] = {
            "cargo": bind("self_knowledge", "experience_role_pt", locator, experience["cargo"]),
            "empresa": bind("self_knowledge", "experience_company_pt", locator, experience["empresa"]),
            "periodo": bind("self_knowledge", "experience_period_pt", locator, experience["periodo"]),
            "bullets": [
                bind("self_knowledge", "experience_bullet_pt", f"{locator}::{index}", bullet)
                for index, bullet in enumerate(experience["bullets"])
            ],
        }
    for mapping in payload["ats_keyword_coverage"]:
        experience_id = str(mapping["experience_id"])
        mapping["evidence_id"] = bind(
            "self_knowledge",
            "ats_evidence",
            _experience_source_locator(experience_id),
            mapping["defensible_evidence"],
        )
    for support in payload["summary_support"]:
        experience_id = str(support["experience_id"])
        support["evidence_id"] = bind(
            "self_knowledge",
            "summary_evidence",
            _experience_source_locator(experience_id),
            support["defensible_evidence"],
        )
    education_evidence = []
    for index, _ in enumerate(payload["education"]):
        source, locator = _education_source_locator(index)
        education_evidence.append(bind(source, "education", locator, payload["education"][index]))
    payload["claim_provenance"] = {
        "summary": [item["evidence_id"] for item in payload["summary_support"]],
        "education": education_evidence,
        "languages": [bind("profile", "language", "Idiomas:", value) for value in payload["languages"]],
        "stack": bind("profile", "technical_stack", "Stack técnica:", payload["stack"]),
        "candidate": {
            key: bind("profile", f"candidate_{key}", value, value)
            for key, value in payload["candidate"].items()
        },
    }
    payload["metadata"]["candidate_facts"] = {
        "revision": revision,
        "sources": catalog,
        "evidence": evidence,
    }


def validate_canonical_provenance(payload: dict[str, Any]) -> None:
    """Resolve every submitted evidence ID against canonical source bytes."""
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    facts = metadata.get("candidate_facts") if isinstance(metadata.get("candidate_facts"), dict) else {}
    if facts.get("revision") != metadata.get("candidate_facts_revision"):
        raise ValidationFailure("CV candidate facts revision mismatch")
    sources = facts.get("sources") if isinstance(facts.get("sources"), dict) else {}
    evidence = facts.get("evidence") if isinstance(facts.get("evidence"), dict) else {}
    if not sources or not evidence:
        raise ValidationFailure("CV canonical evidence catalog is missing")
    for source in sources.values():
        path = Path(str(source.get("path") or ""))
        if not path.is_file() or sha256_file(path) != source.get("sha256"):
            raise ValidationFailure("CV canonical evidence source changed")
    for item in evidence.values():
        source_name = str(item.get("source") or "")
        locator = str(item.get("locator") or "")
        path_record = sources.get(source_name) if isinstance(sources, dict) else None
        if not isinstance(path_record, dict):
            raise ValidationFailure("CV evidence references an unknown canonical source")
        source_path = Path(str(path_record.get("path") or ""))
        if (
            not locator
            or not str(item.get("kind") or "")
            or not str(item.get("value_sha256") or "")
            or _normalize(locator.split("::", 1)[0]) not in _normalize(source_path.read_text(encoding="utf-8"))
        ):
            raise ValidationFailure("CV evidence locator cannot be resolved")
    required: list[str] = []
    def require(item_id: Any, kind: str, value: Any) -> None:
        item_id = str(item_id or "")
        required.append(item_id)
        record = evidence.get(item_id)
        if not isinstance(record, dict) or record.get("kind") != kind:
            raise ValidationFailure("CV evidence kind cannot be resolved")
        if record.get("value_sha256") != hashlib.sha256(str(value).encode("utf-8")).hexdigest():
            raise ValidationFailure("CV evidence value hash mismatch")

    for experience in payload.get("experiences", []):
        require(experience.get("evidence_id"), "experience", experience.get("experience_id"))
        provenance = experience.get("provenance") if isinstance(experience.get("provenance"), dict) else {}
        for key in ("role", "company", "period"):
            require(provenance.get(key), f"experience_{key}", experience.get(key))
        for bullet in experience.get("bullets", []):
            require(bullet.get("evidence_id"), "experience_bullet", bullet.get("text"))
    for experience in payload.get("experiencias", []):
        require(experience.get("evidence_id"), "experience_pt", experience.get("experience_id"))
        provenance = experience.get("provenance") if isinstance(experience.get("provenance"), dict) else {}
        pt_kinds = {
            "cargo": "experience_role_pt",
            "empresa": "experience_company_pt",
            "periodo": "experience_period_pt",
        }
        for key, kind in pt_kinds.items():
            require(provenance.get(key), kind, experience.get(key))
        for item_id, bullet in zip(provenance.get("bullets", []), experience.get("bullets", []), strict=True):
            require(item_id, "experience_bullet_pt", bullet)
    for mapping in payload.get("ats_keyword_coverage", []):
        require(mapping.get("evidence_id"), "ats_evidence", mapping.get("defensible_evidence"))
    for item in payload.get("summary_support", []):
        require(item.get("evidence_id"), "summary_evidence", item.get("defensible_evidence"))
    claims = payload.get("claim_provenance") if isinstance(payload.get("claim_provenance"), dict) else {}
    for item_id, value in zip(claims.get("education", []), payload.get("education", []), strict=True):
        require(item_id, "education", value)
    for item_id, value in zip(claims.get("languages", []), payload.get("languages", []), strict=True):
        require(item_id, "language", value)
    require(claims.get("stack"), "technical_stack", payload.get("stack"))
    for key, value in payload.get("candidate", {}).items():
        require((claims.get("candidate") or {}).get(key), f"candidate_{key}", value)
    if not required or any(item not in evidence for item in required):
        raise ValidationFailure("CV evidence ID cannot be resolved against canonical facts")


def _english_period(period: str) -> str:
    months = {
        "jan": "Jan", "janeiro": "Jan", "fev": "Feb", "fevereiro": "Feb",
        "mar": "Mar", "março": "Mar", "abr": "Apr", "abril": "Apr",
        "mai": "May", "maio": "May", "jun": "Jun", "junho": "Jun",
        "jul": "Jul", "julho": "Jul", "ago": "Aug", "agosto": "Aug",
        "set": "Sep", "setembro": "Sep", "out": "Oct", "outubro": "Oct",
        "nov": "Nov", "novembro": "Nov", "dez": "Dec", "dezembro": "Dec",
    }
    translated = period
    for source, target in months.items():
        translated = re.sub(rf"\b{source}(?=/|\s)", target, translated, flags=re.IGNORECASE)
    return translated.replace("Atual", "Present").replace("/", " ")


def _experience_source_locator(experience_id: str) -> str:
    locators = {
        "wehandle_head_operacoes": "wehandle",
        "ifood_diretor_operacoes": "Ifood",
        "ifood_head_operacoes": "Ifood",
        "renault_cs": "Renault do Brasil",
        "vivareal_planejamento_operacoes": "VivaReal",
        "trifil_sop": "Coordenador de S&OP",
        "trifil_inteligencia_comercial": "Coordenador de Inteligência Comercial",
    }
    return locators[experience_id]


def _education_source_locator(index: int) -> tuple[str, str]:
    locators = (
        ("profile", "BSP Business School São Paulo"),
        ("self_knowledge", "Engenheiro Químico — Faculdades Oswaldo Cruz"),
        ("self_knowledge", "Six Sigma Green Belt - Setec Consulting"),
    )
    return locators[index]
