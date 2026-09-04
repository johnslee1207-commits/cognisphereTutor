"""Add Tutor-ready radar modules to bundled domain packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BUNDLE_DIR = Path("cognispheretutor/integrations/cognisphere/bundled_packs")
STORE_DIR = Path("data/user/workspace/learning")
IMPORT_CACHE_DIR = Path("data/user/workspace/cognisphere_imports")


def kp(
    item_id: str,
    name: str,
    kp_type: str = "concept",
    *,
    module_id: str,
) -> dict[str, Any]:
    return {"id": item_id, "name": name, "type": kp_type, "module_id": module_id}


def module(module_id: str, name: str, order: int, points: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "id": module_id,
        "name": name,
        "order": order,
        "pass_threshold": 0.7,
        "knowledge_points": [
            kp(item_id, title, kp_type, module_id=module_id)
            for item_id, title, kp_type in points
        ],
    }


def aws_modules() -> list[dict[str, Any]]:
    bid = "csphere-aws_certification"
    return [
        module(
            f"{bid}-cloud-foundations",
            "AWS Cloud Foundations",
            0,
            [
                ("aws-cloud-value-proposition", "Cloud value proposition and pay-as-you-go economics", "concept"),
                ("aws-global-infrastructure", "AWS Regions, Availability Zones, edge locations, and global reach", "concept"),
                ("aws-shared-responsibility", "Shared Responsibility Model and customer responsibilities", "concept"),
                ("aws-cloud-deployment-models", "Public, private, hybrid, and multi-cloud deployment models", "concept"),
                ("aws-migration-modernization", "Migration, modernization, and common cloud adoption drivers", "concept"),
                ("aws-well-architected-overview", "Well-Architected pillars as certification reasoning lenses", "concept"),
            ],
        ),
        module(
            f"{bid}-clf-cloud-concepts",
            "CLF-C02 Cloud Concepts",
            1,
            [
                ("aws-clf-cloud-concepts", "CLF-C02 cloud concepts and business value", "concept"),
                ("aws-clf-design-principles", "Cloud design principles: scalability, elasticity, agility, and high availability", "concept"),
                ("aws-clf-economies-scale", "Economies of scale and shift from capital expense to variable expense", "concept"),
                ("aws-clf-global-benefits", "Benefits of global reach, low latency, fault tolerance, and disaster recovery", "concept"),
                ("aws-clf-managed-services", "Managed services and the operational value of undifferentiated lifting", "concept"),
                ("aws-clf-well-architected-pillars", "Well-Architected pillars in Cloud Practitioner scenarios", "concept"),
                ("aws-clf-migration-value", "Business value of migration, modernization, and cloud adoption frameworks", "concept"),
                ("aws-clf-cloud-concepts-quiz", "Quick-check cloud concepts with certification-style answer elimination", "procedure"),
            ],
        ),
        module(
            f"{bid}-clf-security-compliance",
            "CLF-C02 Security and Compliance",
            2,
            [
                ("aws-clf-security-compliance", "CLF-C02 security, compliance, IAM, and shared responsibility", "concept"),
                ("aws-iam-users-groups-roles", "IAM users, groups, roles, policies, and least privilege", "concept"),
                ("aws-root-mfa-best-practices", "Root account protection, MFA, and access key hygiene", "procedure"),
                ("aws-security-services", "Security Hub, GuardDuty, Inspector, WAF, Shield, and Macie use cases", "concept"),
                ("aws-encryption-kms", "Encryption at rest and in transit with KMS and managed keys", "concept"),
                ("aws-compliance-artifacts", "AWS Artifact, compliance programs, and customer audit responsibilities", "concept"),
                ("aws-monitoring-audit", "CloudTrail, CloudWatch, Config, and audit evidence basics", "concept"),
                ("aws-security-quiz", "Security scenario quick quiz and misconception review", "procedure"),
            ],
        ),
        module(
            f"{bid}-clf-technology-services",
            "CLF-C02 Technology Services",
            3,
            [
                ("aws-clf-technology-services", "CLF-C02 core technology services: compute, storage, database, network", "concept"),
                ("aws-compute-ec2", "EC2 instances, AMIs, instance families, and basic compute choices", "concept"),
                ("aws-compute-lambda-containers", "Lambda, ECS, EKS, and container/serverless tradeoffs", "concept"),
                ("aws-storage-s3", "S3 buckets, storage classes, lifecycle, versioning, and durability", "concept"),
                ("aws-storage-ebs-efs", "EBS, EFS, FSx, and block/file storage selection", "concept"),
                ("aws-databases-rds-dynamodb", "RDS, Aurora, DynamoDB, ElastiCache, and database fit", "concept"),
                ("aws-clf-vpc-networking", "VPC, subnets, security groups, route tables, and connectivity basics", "concept"),
                ("aws-network-edge", "Route 53, CloudFront, Global Accelerator, and edge networking", "concept"),
                ("aws-integration-messaging", "SQS, SNS, EventBridge, Step Functions, and decoupled systems", "concept"),
                ("aws-clf-monitoring", "CloudWatch, CloudTrail, Trusted Advisor, and basic operations", "concept"),
                ("aws-ai-analytics-overview", "Analytics, machine learning, and AI services at Cloud Practitioner depth", "concept"),
                ("aws-technology-services-quiz", "Service-selection quick quiz using scenario clues", "procedure"),
            ],
        ),
        module(
            f"{bid}-clf-billing-cost",
            "CLF-C02 Billing, Pricing, and Support",
            4,
            [
                ("aws-clf-billing-pricing", "CLF-C02 billing, pricing, support, and cost tools", "concept"),
                ("aws-pricing-models", "On-Demand, Reserved Instances, Savings Plans, Spot, and free tier", "concept"),
                ("aws-cost-tools", "Cost Explorer, Budgets, Pricing Calculator, CUR, and cost allocation tags", "procedure"),
                ("aws-support-plans", "AWS Support plans, Trusted Advisor checks, and account help paths", "concept"),
                ("aws-organizations-billing", "Organizations, consolidated billing, SCPs, and multi-account basics", "concept"),
                ("aws-cost-quiz", "Billing and cost scenario quick quiz", "procedure"),
            ],
        ),
        module(
            f"{bid}-associate-preview-exam-practice",
            "Associate Preview and Exam Practice",
            5,
            [
                ("aws-associate-paths-overview", "Choose next Associate path: Solutions Architect, Developer, or SysOps", "concept"),
                ("aws-saa-resilient-architectures", "Preview resilient architectures with Multi-AZ, load balancing, and decoupling", "procedure"),
                ("aws-saa-secure-networked-access", "Preview secure networked access with IAM, encryption, and VPC boundaries", "procedure"),
                ("aws-exam-domain-map", "Map questions to official exam domains before answering", "procedure"),
                ("aws-exam-scenario-elimination", "Use scenario clues and eliminate unsafe or overbuilt answers", "procedure"),
                ("aws-exam-review-loop", "Use quick quizzes, error memory, mock review, and source-grounded remediation", "procedure"),
            ],
        ),
    ]


def ap_modules() -> list[dict[str, Any]]:
    bid = "csphere-ap_calculus"
    return [
        module(
            f"{bid}-limits-continuity",
            "AP Calculus Limits and Continuity",
            0,
            [
                ("ap-limits-intuition", "Limits from graphs, tables, and algebraic behavior", "concept"),
                ("ap-continuity", "Continuity, removable discontinuities, and one-sided limits", "concept"),
                ("ap-limit-techniques", "Algebraic limit techniques and squeeze-style reasoning", "procedure"),
            ],
        ),
        module(
            f"{bid}-derivatives",
            "AP Calculus Derivatives",
            1,
            [
                ("ap-derivative-definition", "Derivative meaning: rate of change and tangent slope", "concept"),
                ("ap-derivative-rules", "Power, product, quotient, chain, implicit, and inverse derivative rules", "procedure"),
                ("ap-derivative-applications", "Motion, related rates, optimization, and graph behavior", "procedure"),
                ("ap-derivative-graph-interpretation", "Connect f, f prime, and f double-prime graphs", "procedure"),
            ],
        ),
        module(
            f"{bid}-integrals",
            "AP Calculus Integrals and FTC",
            2,
            [
                ("ap-integral-meaning", "Definite integrals as accumulation and net change", "concept"),
                ("ap-antiderivatives", "Antiderivatives, substitution, and basic integration techniques", "procedure"),
                ("ap-ftc", "Fundamental Theorem of Calculus in graph, table, and symbolic contexts", "procedure"),
                ("ap-area-volume", "Area, volume, and accumulation applications", "procedure"),
            ],
        ),
        module(
            f"{bid}-differential-equations",
            "AP Calculus Differential Equations",
            3,
            [
                ("ap-slope-fields", "Slope fields and solution curve reasoning", "concept"),
                ("ap-separable-differential-equations", "Separable differential equations and initial conditions", "procedure"),
                ("ap-exponential-logistic-models", "Exponential and logistic models", "procedure"),
            ],
        ),
        module(
            f"{bid}-series-bc",
            "AP Calculus BC Series",
            4,
            [
                ("ap-sequence-series-basics", "Sequences, series, convergence, and divergence", "concept"),
                ("ap-series-tests", "Geometric, p-series, comparison, ratio, alternating, and integral tests", "procedure"),
                ("ap-power-series", "Power series, radius/interval of convergence, and representation", "procedure"),
                ("ap-taylor-series", "Taylor and Maclaurin polynomials and error reasoning", "procedure"),
            ],
        ),
        module(
            f"{bid}-exam-frq-practice",
            "AP Calculus Exam Practice",
            5,
            [
                ("ap-mcq-strategy", "Multiple-choice strategy: classify, compute, estimate, eliminate", "procedure"),
                ("ap-frq-communication", "Free-response communication: setup, notation, units, and justification", "procedure"),
                ("ap-error-review", "Error review by concept, algebra, notation, and interpretation", "procedure"),
                ("ap-readiness-checkpoint", "AB/BC readiness checkpoint using mixed AP-style tasks", "procedure"),
            ],
        ),
    ]


def leetcode_modules() -> list[dict[str, Any]]:
    bid = "csphere-leetcode"
    return [
        module(
            f"{bid}-problem-solving-foundations",
            "LeetCode Problem-Solving Foundations",
            0,
            [
                ("lc-problem-reading", "Read constraints, examples, input/output, and edge cases", "procedure"),
                ("lc-complexity-basics", "Time and space complexity basics", "concept"),
                ("lc-test-first-thinking", "Create examples and counterexamples before coding", "procedure"),
            ],
        ),
        module(
            f"{bid}-arrays-hashmaps-strings",
            "Arrays, Hash Maps, and Strings",
            1,
            [
                ("lc-array-iteration", "Array iteration, prefix state, and boundary handling", "procedure"),
                ("lc-hashmap-lookup", "Hash map counting, indexing, and complement lookup", "procedure"),
                ("lc-string-patterns", "String scanning, frequency maps, and normalization", "procedure"),
            ],
        ),
        module(
            f"{bid}-two-pointers-sliding-window",
            "Two Pointers and Sliding Window",
            2,
            [
                ("lc-two-pointers", "Two-pointer invariants and sorted/paired movement", "procedure"),
                ("lc-sliding-window", "Sliding-window expand/shrink conditions", "procedure"),
                ("lc-window-invariants", "Maintain window state without off-by-one errors", "procedure"),
            ],
        ),
        module(
            f"{bid}-recursion-trees-graphs",
            "Recursion, Trees, and Graphs",
            3,
            [
                ("lc-recursion-backtracking", "Recursion, backtracking state, and base cases", "procedure"),
                ("lc-tree-traversal", "Tree traversal and divide-and-conquer reasoning", "procedure"),
                ("lc-graph-bfs-dfs", "Graph BFS/DFS, visited state, and shortest path basics", "procedure"),
            ],
        ),
        module(
            f"{bid}-dynamic-programming",
            "Dynamic Programming",
            4,
            [
                ("lc-dp-state", "DP state definition and recurrence", "procedure"),
                ("lc-dp-order", "DP traversal order, base cases, and transitions", "procedure"),
                ("lc-dp-optimization", "Space optimization and memoization tradeoffs", "procedure"),
            ],
        ),
        module(
            f"{bid}-interview-readiness",
            "Interview Readiness",
            5,
            [
                ("lc-explain-approach", "Explain approach, correctness, and complexity", "procedure"),
                ("lc-debugging", "Debug with traces, edge cases, and invariant checks", "procedure"),
                ("lc-timed-practice", "Timed mock practice and post-solve error review", "procedure"),
            ],
        ),
    ]


def apply_bundle_modules(domain: str, modules: list[dict[str, Any]]) -> None:
    path = BUNDLE_DIR / f"{domain}_bundle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("knowledge", {})["mastery_modules"] = modules
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_import_cache_modules(domain: str, modules: list[dict[str, Any]]) -> bool:
    path = IMPORT_CACHE_DIR / domain / "bundle.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("knowledge", {})["mastery_modules"] = modules
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_store_modules(domain: str, modules: list[dict[str, Any]]) -> bool:
    path = STORE_DIR / f"csphere-{domain}.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    old_kps = {
        kp.get("id")
        for mod in data.get("modules", [])
        for kp in mod.get("knowledge_points", [])
        if isinstance(kp, dict)
    }
    new_kps = {
        kp.get("id")
        for mod in modules
        for kp in mod.get("knowledge_points", [])
        if isinstance(kp, dict)
    }
    data["modules"] = modules
    for key in ("mastery_levels", "knowledge_types", "repetition_states", "feynman_retries", "feynman_explanations"):
        if isinstance(data.get(key), dict):
            data[key] = {k: v for k, v in data[key].items() if k in new_kps}
    if isinstance(data.get("review_queue"), list):
        data["review_queue"] = [
            item for item in data["review_queue"] if item.get("knowledge_point_id") in new_kps
        ]
    if isinstance(data.get("error_records"), list):
        data["error_records"] = [
            item for item in data["error_records"] if item.get("knowledge_point_id") in new_kps
        ]
    if old_kps != new_kps:
        data["current_module_id"] = modules[0]["id"] if modules else None
        data["current_kp_index"] = 0
        data["current_stage"] = "explain"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    domain_modules = {
        "aws_certification": aws_modules(),
        "ap_calculus": ap_modules(),
        "leetcode": leetcode_modules(),
    }
    result: dict[str, dict[str, Any]] = {}
    for domain, modules in domain_modules.items():
        apply_bundle_modules(domain, modules)
        cache_migrated = apply_import_cache_modules(domain, modules)
        migrated = migrate_store_modules(domain, modules)
        result[domain] = {
            "modules": len(modules),
            "knowledge_points": sum(len(m.get("knowledge_points", [])) for m in modules),
            "import_cache_migrated": cache_migrated,
            "store_migrated": migrated,
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
