export const EVAL_EXAMPLE_QUESTIONS = [
  "What years are covered in the total deaths by single year of age data provided in the OIA0743 JOB-12557 spreadsheet?",
  "What were the Moehau 2021 communication-plan contacts meant to be told about the operation?",
  "Where can I find the data on people who died or were hospitalised from supplements between 2013 and 2021?",
  "When does the NZ police force currently conduct alcohol and drug testing?",
  "What is the estimated annual cost per seat for Adobe Acrobat Professional based on the Adobe website pricing mentioned in the response?",
  "Who was the author of the November 2018 version 2.3 of the MBIE Privacy Policy?",
  "Have any Crown Irrigation Investments Limited board members recused themselves from votes regarding the Central Plains Water investment due to conflicts of interest?",
  "How many PHMS were coming in on Friday for up-skilling and to support ARPHS according to the August 18 update?",
  "Where did the worst characteristic stiffness and tensile strength occur in radiata pine butt logs?",
  "What is the routine service check frequency for the hanging grab handles in the Tranzit fleet?",
  "How many complaints regarding LGBT discrimination have been received by WorkSafe New Zealand's Human Resources department and what was the outcome?",
  "What was the title of the submission made to the Minister of Foreign Affairs on 9 November 2021 regarding the offshore post network?",
  "Who authored the briefing provided to Justice Minister Simon Power on 12 March 2009 regarding the Peter Ellis case?",
  "What is the maximum percentage increase in fees that the Minister of State Services can agree to without referring it to the Cabinet Appointments and Honours Committee and Cabinet?",
  "For Auckland Council pools and leisure centres, how many fatal drownings, non-fatal drownings, and other lifeguard-attended events were recorded for contracted operators?",
  "What did Auckland Council request 8140014852 cover for leisure centres managed by council versus under contract?",
];

const DEFAULT_EXAMPLE_COUNT = 3;

export function selectRandomExampleQuestions(
  questions: readonly string[],
  random: () => number = Math.random,
  count = DEFAULT_EXAMPLE_COUNT,
): string[] {
  const remaining = Array.from(new Set(questions));
  const selected: string[] = [];
  while (remaining.length > 0 && selected.length < count) {
    const index = Math.min(remaining.length - 1, Math.floor(random() * remaining.length));
    const [question] = remaining.splice(index, 1);
    if (question) {
      selected.push(question);
    }
  }
  return selected;
}
