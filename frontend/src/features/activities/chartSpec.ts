type ChartObject = Record<string, unknown>

const LINE_MARKS = new Set(['line', 'trail'])
const ZERO_BASELINE_MARKS = new Set(['area', 'bar'])
const COMPOSITION_KEYS = ['concat', 'hconcat', 'layer', 'vconcat'] as const

function isObject(value: unknown): value is ChartObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function markType(mark: unknown): string | null {
  if (typeof mark === 'string') return mark
  if (isObject(mark) && typeof mark.type === 'string') return mark.type
  return null
}

function collectLayerMarks(spec: ChartObject, marks: Set<string>) {
  const type = markType(spec.mark)
  if (type) marks.add(type)

  if (!Array.isArray(spec.layer)) return
  for (const layer of spec.layer) {
    if (isObject(layer)) collectLayerMarks(layer, marks)
  }
}

function usesTightLineDomain(spec: ChartObject): boolean {
  const directMark = markType(spec.mark)
  if (directMark && LINE_MARKS.has(directMark)) return true
  if (!Array.isArray(spec.layer)) return false

  const marks = new Set<string>()
  collectLayerMarks(spec, marks)
  return (
    [...marks].some((mark) => LINE_MARKS.has(mark)) &&
    ![...marks].some((mark) => ZERO_BASELINE_MARKS.has(mark))
  )
}

function tightenQuantitativeYScale(encoding: ChartObject): ChartObject {
  const y = encoding.y
  if (!isObject(y) || y.type !== 'quantitative') return encoding

  const scale = y.scale
  if (scale === null || (scale !== undefined && !isObject(scale))) return encoding
  if (isObject(scale) && ('domain' in scale || 'zero' in scale)) return encoding

  return {
    ...encoding,
    y: {
      ...y,
      scale: {
        ...(isObject(scale) ? scale : {}),
        zero: false,
      },
    },
  }
}

/**
 * Vega-Lite includes zero in quantitative position scales by default. That is
 * essential for bars and areas, but it can flatten small changes in a line.
 * Tighten only line-based Y domains and preserve every explicit scale choice.
 */
export function withReadableLineScales(spec: ChartObject): ChartObject {
  const normalized: ChartObject = { ...spec }

  for (const key of COMPOSITION_KEYS) {
    const children = spec[key]
    if (!Array.isArray(children)) continue
    normalized[key] = children.map((child) =>
      isObject(child) ? withReadableLineScales(child) : child,
    )
  }

  if (isObject(spec.spec)) {
    normalized.spec = withReadableLineScales(spec.spec)
  }

  if (usesTightLineDomain(spec) && isObject(spec.encoding)) {
    normalized.encoding = tightenQuantitativeYScale(spec.encoding)
  }

  return normalized
}
