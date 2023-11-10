export interface StepSpec {
  action: ['goto' | 'click', ...string[]],
  origin?: {
    location: string,
    tagName: string,
    textContent: string,
    attributes: { [key: string]: string },
  },
}

export interface JobSpec {
  priority: number,
  depth: number,
  steps: StepSpec[],
}
