export type HallDiscussionDomain =
  | "engineering"
  | "creative"
  | "analysis"
  | "product"
  | "research"
  | "operations"
  | "general";

interface DomainSignal {
  pattern: RegExp;
  weight: number;
}

const DOMAIN_SIGNAL_MAP: Record<Exclude<HallDiscussionDomain, "general">, DomainSignal[]> = {
  engineering: [
    { pattern: /(代码|编程|开发|工程|接口|api|bug|debug|fix|implement|build|frontend|backend|repo|system)/i, weight: 4 },
    { pattern: /(测试|test|lint|deploy|发布脚本|服务端|前端页面|数据库|schema|migration)/i, weight: 3 },
  ],
  creative: [
    { pattern: /(动画|动效|animation|motion|storyboard|分镜|脚本|style frame|视觉语言|品牌|创意)/i, weight: 4 },
    { pattern: /(海报|设计稿|视觉稿|art direction|创意方向|叙事体验)/i, weight: 3 },
    { pattern: /(visual|可视化)/i, weight: 1 },
  ],
  analysis: [
    { pattern: /(数据|图表|dashboard|指标|分析|insight|metric|analytics)/i, weight: 3 },
    { pattern: /(可视化|visualization|narrative|storytelling with data)/i, weight: 2 },
  ],
  product: [
    { pattern: /(产品|发布|roadmap|增长|launch|go[- ]to[- ]market|workflow|feature|scope|success criteria)/i, weight: 3 },
    { pattern: /(用户|体验|user problem|需求范围|优先级|产品方向)/i, weight: 1 },
  ],
  research: [
    { pattern: /(调研|research|benchmark|study|compare|调查|访谈|洞察|评估|研究问题)/i, weight: 4 },
    { pattern: /(证据|evidence|结论结构|假设|synthesis|调查视角|研究框架)/i, weight: 3 },
  ],
  operations: [
    { pattern: /(运营|流程|排期|runbook|support|审批|交接|上线|通知|治理)/i, weight: 3 },
    { pattern: /(handoff|handover|流程设计|责任边界|试运行|值班|incident)/i, weight: 2 },
  ],
};

const DOMAIN_TIE_BREAK_ORDER: HallDiscussionDomain[] = [
  "engineering",
  "research",
  "creative",
  "analysis",
  "product",
  "operations",
  "general",
];

export function inferHallDiscussionDomainFromText(source: string): HallDiscussionDomain {
  const normalized = source.toLowerCase();
  const scored = Object.entries(DOMAIN_SIGNAL_MAP).map(([domain, signals]) => ({
    domain: domain as HallDiscussionDomain,
    score: signals.reduce((total, signal) => total + (signal.pattern.test(normalized) ? signal.weight : 0), 0),
  }));
  const bestScore = scored.reduce((max, item) => Math.max(max, item.score), 0);
  if (bestScore <= 0) return "general";
  const candidates = scored
    .filter((item) => item.score === bestScore)
    .map((item) => item.domain);
  return DOMAIN_TIE_BREAK_ORDER.find((domain) => candidates.includes(domain)) ?? "general";
}
