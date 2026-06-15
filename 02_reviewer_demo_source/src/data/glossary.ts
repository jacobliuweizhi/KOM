import { termDefinitions } from './termDefinitions';

export const glossary = termDefinitions.map((term) => [term.key, `${term.english}; ${term.chinese}. ${term.definition}`] as const);
