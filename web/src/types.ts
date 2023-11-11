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
  parents: string[],
  steps: StepSpec[],
}

export interface ElementInformation {
  outerHTML: string;
  tagName: string;
  attributes: { [key: string]: string };
  text: string;
}

export interface WebFormField {
  name: string;
  fieldElement: ElementInformation;
  labelElement: ElementInformation | null;
}

export interface WebForm {
  defaultFormData: { [key: string]: string };
  element: ElementInformation;
  fields: WebFormField[];
}
