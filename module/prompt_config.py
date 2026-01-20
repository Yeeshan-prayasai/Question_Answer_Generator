"""
Configuration for Prompt Crafter.
Stores descriptions and examples for Question Patterns, Cognitive Complexities, and Difficulty Levels.
"""

PROMPT_CONFIG = {
    "patterns": {
        "Standard Single-Correct": {
            "description": """
        1.  **Format:** The question MUST have options where **ONLY ONE** choice is correct.
        2.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        3.  **Options:** Options must be concise (single word or phrase is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to the correct answer to make subtle distinctions challenging.
        4.  **Avoid Simplicity:** When testing knowledge of systems or large topics (e.g., river systems, constitutional bodies, economic policy), **NEVER** use the most obvious or famous examples. Instead, target obscure, but still relevant, details.
            """,
            "example": """
Question:
Which one of the following best describes the term 'Green Hydrogen'?

Options:
(a) Hydrogen produced from the electrolysis of water using renewable energy sources.
(b) Hydrogen produced from fossil fuels, with the associated carbon emissions captured and stored.
(c) Hydrogen that is produced as a by-product of industrial chemical processes.
(d) Hydrogen that is naturally occurring in geological formations.

Answer: A
            """
        },
        "Standard Single-Incorrect": {
            "description": """
        1.  **Format:** The question MUST have options where **ONLY ONE** choice is Incorrect.
        2.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        3.  **Options:** Options must be concise (single word or phrase is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to the correct answer to make subtle distinctions challenging.
        4.  **Avoid Simplicity:** When testing knowledge of systems or large topics, **NEVER** use the most obvious or famous examples. Instead, target obscure, but still relevant, details.
            """,
            "example": """
Question:
Which one of the following was NOT a feature of the Government of India Act of 1919?

Options:
(a) It introduced 'dyarchy' in the executive government of the provinces.
(b) It introduced separate communal electorates for Sikhs, Indian Christians, and Anglo-Indians.
(c) It provided for the establishment of a Public Service Commission.
(d) It provided for the establishment of an All-India Federation with provinces and princely states.

Answer: D
            """
        },
        "Multiple-Statement-2 (Correct)": {
            "description": """
        1.  **Format:** The question MUST have multiple small statements, options will test about knowledge of each statement to finalize answer.
        2.  **MANDATORY STRUCTURE:** Every multi-statement question MUST include:
            * **Opening context:** Begin with an introductory phrase such as "With reference to...", "Consider the following statements about...", "Consider the following statements regarding...", etc.
            * **Closing question:** End with "Which of the statements given above is/are correct?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Statements:** Statements must be concise and small (single phrase or at most small line is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions and elimination challenging.
            """,
            "example": """
Question:
Consider the following statements about Raja Ram Mohan Roy :

I. He possessed great love and respect for the traditional philosophical systems of the East.
II. He desired his countrymen to accept the rational and scientific approach and the principle of human dignity and social equality of all men and women.

Which of the statements given above is/are correct?

Options:
(a) I only
(b) II only
(c) Both I and II
(d) Neither I nor II

Answer: C
            """
        },
        "Multiple-Statement-3 (Correct)": {
            "description": """
        1.  **Format:** The question MUST have multiple small statements, options will test about knowledge of each statement to finalize answer.
        2.  **MANDATORY STRUCTURE:** Every multi-statement question MUST include:
            * **Opening context:** Begin with an introductory phrase such as "With reference to...", "Consider the following statements about...", "Consider the following statements regarding...", etc.
            * **Closing question:** End with "Which of the statements given above is/are correct?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Statements:** Statements must be concise and small (single phrase or at most small line is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions and elimination challenging.
            """,
            "example": """
Question:
With reference to the office of the President of India, consider the following statements:

1. The President is elected by an electoral college consisting of all members of Parliament and all members of State Legislative Assemblies.
2. The President's election is held in accordance with the system of proportional representation by means of the single transferable vote.
3. The President holds office for a term of five years and is eligible for re-election.

Which of the statements given above is/are correct?

Options:
(a) 1 and 2 only
(b) 2 and 3 only
(c) 1 and 3 only
(d) 1, 2 and 3
Answer: B
            """
        },
        "Multiple-Statement-2 (Incorrect)": {
            "description": """
        1.  **Format:** The question MUST have exactly 2 small statements, options will test about knowledge of each statement to finalize answer.
        2.  **MANDATORY STRUCTURE:** Every multi-statement question MUST include:
            * **Opening context:** Begin with an introductory phrase such as "With reference to...", "Consider the following statements about...", "Consider the following statements regarding...", etc.
            * **Closing question:** End with "Which of the statements given above is/are NOT correct?" or "Which of the statements given above are incorrect?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Statements:** Statements must be concise and small (single phrase or at most small line is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions and elimination challenging.
        5.  **CRITICAL:** This pattern requires EXACTLY 2 statements (I and II or 1 and 2). Do not include more.
            """,
            "example": """
Question:
Consider the following statements regarding 'Aerosols':

I. Aerosols are tiny solid or liquid particles suspended in the atmosphere.
II. Aerosols always have a warming effect on the climate.

Which of the statements given above is/are NOT correct?

Options:
(a) I only
(b) II only
(c) Both I and II
(d) Neither I nor II

Answer: B
            """
        },
        "Multiple-Statement-3 (Incorrect)": {
            "description": """
        1.  **Format:** The question MUST have exactly 3 small statements, options will test about knowledge of each statement to finalize answer.
        2.  **MANDATORY STRUCTURE:** Every multi-statement question MUST include:
            * **Opening context:** Begin with an introductory phrase such as "With reference to...", "Consider the following statements about...", "Consider the following statements regarding...", etc.
            * **Closing question:** End with "Which of the statements given above is/are NOT correct?" or "Which of the statements given above are incorrect?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Statements:** Statements must be concise and small (single phrase or at most small line is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions and elimination challenging.
        5.  **CRITICAL:** This pattern requires EXACTLY 3 statements (numbered 1, 2, 3). Do not include more or fewer.
            """,
            "example": """
Question:
Consider the following statements regarding the 'Black Cotton Soils' (Regur soils) of India:

1. They are formed from the weathering of basaltic rocks.
2. They are rich in phosphoric acid, nitrogen, and organic matter.
3. They possess a high moisture-retention capacity.

Which of the statements given above is/are NOT correct?

Options:
(a) 1 and 3 only
(b) 2 only
(c) 1 and 2 only
(d) 3 only

Answer: B
            """
        },
        "Multiple-Statement-4 (Correct)": {
            "description": """
        1.  **Format:** The question MUST have exactly 4 small statements.
        2.  **MANDATORY STRUCTURE:**
            * **Opening context:** Begin with "With reference to...", "Consider the following statements...", etc.
            * **Closing question:** End with "Which of the statements given above is/are correct?"
        3.  **CRITICAL - ALL 4 STATEMENTS REQUIRED:**
            * Include EXACTLY 4 statements numbered 1, 2, 3, 4
            * Statement 4 MUST be present and complete - DO NOT stop at statement 3
            * The closing question "Which of the statements given above is/are correct?" MUST appear AFTER statement 4
        4.  **EXACT STRUCTURE TO FOLLOW:**
            ```
            [Opening context - e.g., "With reference to X, consider the following statements:"]

            1. [Statement 1]
            2. [Statement 2]
            3. [Statement 3]
            4. [Statement 4]

            Which of the statements given above is/are correct?
            ```
        5.  **Statements:** Concise, TOUGH, and CLOSELY RELATED for challenging distinctions.
        6.  **FAILURE CONDITIONS:** Question is INVALID if: (a) Missing statement 4, OR (b) Missing closing question after statements.
            """,
            "example": """
Question:
With reference to the Indian Constitution, consider the following statements:

1. The Constitution provides for a parliamentary form of government at the Centre and in the States.
2. The President of India is directly elected by the people.
3. The Vice President is the ex-officio Chairman of the Rajya Sabha.
4. The Supreme Court has the power of judicial review.

Which of the statements given above is/are correct?

Options:
(a) 1, 2 and 3 only
(b) 1, 3 and 4 only
(c) 2, 3 and 4 only
(d) 1, 2, 3 and 4

Answer: B
            """
        },
        "Multiple-Statement-4 (Incorrect)": {
            "description": """
        1.  **Format:** The question MUST have exactly 4 small statements.
        2.  **MANDATORY STRUCTURE:**
            * **Opening context:** Begin with "With reference to...", "Consider the following statements...", etc.
            * **Closing question:** End with "Which of the statements given above is/are NOT correct?"
        3.  **CRITICAL - ALL 4 STATEMENTS REQUIRED:**
            * Include EXACTLY 4 statements numbered 1, 2, 3, 4
            * Statement 4 MUST be present and complete - DO NOT stop at statement 3
            * The closing question "Which of the statements given above is/are NOT correct?" MUST appear AFTER statement 4
        4.  **EXACT STRUCTURE TO FOLLOW:**
            ```
            [Opening context - e.g., "Consider the following statements regarding X:"]

            1. [Statement 1]
            2. [Statement 2]
            3. [Statement 3]
            4. [Statement 4]

            Which of the statements given above is/are NOT correct?
            ```
        5.  **Statements:** Concise, TOUGH, and CLOSELY RELATED for challenging distinctions.
        6.  **FAILURE CONDITIONS:** Question is INVALID if: (a) Missing statement 4, OR (b) Missing closing question after statements.
            """,
            "example": """
Question:
Consider the following statements regarding India's biodiversity:

1. India is one of the 17 mega-diverse countries in the world.
2. The Western Ghats and Eastern Himalayas are recognized as biodiversity hotspots.
3. Project Tiger was launched in 1973 to protect the Bengal Tiger.
4. India has more than 50,000 plant species, making it the most plant-diverse country in the world.
Which of the statements given above is/are NOT correct?
Options:
(a) 1 and 2 only
(b) 2 and 4 only
(c) 3 and 4 only
(d) 4 only

Answer: D
            """
        },
        "How Many - Statement": {
            "description": """
        1.  **Format:** The question MUST have multiple small statements, options will test about knowledge of each statement to finalize answer. Here Elimination is not possible.
        2.  **MANDATORY STRUCTURE:** Every multi-statement question MUST include:
            * **Opening context:** Begin with an introductory phrase such as "Consider the following regarding...", "Consider the following statements...", etc.
            * **Closing question:** End with "How many of the statements given above are correct?" or "How many of the above statements are correct?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Statements:** Statements must be concise and small (single phrase or at most small line is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions and elimination challenging.
            """,
            "example": """
Question:
Consider the following regarding organisms:

1. Agaricus is a type of fungus.
2. Nostoc is a blue-green alga.
3. Spirogyra is a protist.
4. Yeast is used in the production of bread and beer.

How many of the statements given above are correct?

Options:
(a) Only one
(b) Only two
(c) Only three
(d) All four

Answer: C
            """
        },
        "How Many Pairs Correct/Incorrect": {
            "description": """
        1.  **Format:** The question MUST have multiple pairs, options will test associative knowledge of candidate.
        2.  **MANDATORY STRUCTURE:** Every pairs question MUST include:
            * **Opening context:** Begin with "Consider the following pairs:"
            * **Closing question:** End with "How many pairs given above are correctly matched?" or "How many of the above pairs are correctly matched?"
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Pairs:** Pairs must be concise and small (single word is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions challenging.
            """,
            "example": """
Question:
Consider the following pairs:

   Historical Site  :    Well-known for
1. Bhaja           :    Buddhist Cave Shrine
2. Sittanavasal    :    Jain Mural Paintings
3. Ellora          :    Shaivite, Buddhist, and Jain Caves

How many pairs given above are correctly matched?

Options:
(a) Only one pair
(b) Only two pairs
(c) All three pairs
(d) None of the pairs

Answer: B
            """
        },
        "How Many Sets/Triplets": {
            "description": """
        1.  **Format:** The question MUST have multiple triplets, options will test associative knowledge of candidate.
        2.  **MANDATORY STRUCTURE:** Every sets/triplets question MUST include:
            * **Opening context:** Begin with "Consider the following:"
            * **Closing question:** End with "How many of the sets given above are correctly matched in all three aspects?" or similar phrasing
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Triplets:** Triplets must be concise and small (single word is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions challenging.
            """,
            "example": """
Question:
Consider the following:

   Tribe            :    State             :    Primary Festival
1. Konyak          :    Nagaland          :    Aoleang
2. Tharu           :    Uttarakhand       :    Diwali (as a day of mourning)
3. Bhil            :    Madhya Pradesh    :    Bhagoria

How many of the sets given above are correctly matched in all three aspects?

Options:
(a) Only one set
(b) Only two sets
(c) All three sets
(d) None of the sets

Answer: A
            """
        },
        "Std 2-Stmt Assertion-Reason": {
            "description": """
        1.  **Format:** The question MUST have two statements, options will test reasoning knowledge of candidate.
        2.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        3.  **Statements:** Statements must be concise and small (single phrase/sentence is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions challenging.
        4. **DO NOT** frame question such that OPTION A is the answer.[There is a tendency to make OPTION A the correct answer in such questions, which should be avoided.]
            """,
            "example": """
Question:
Consider the following statements:

Statement-I: India, despite having large uranium deposits, depends on coal for most of its electricity production.
Statement-II: Uranium, enriched to the extent of at least 60%, is required for the production of electricity.

Which one of the following is correct in respect of the above statements?

Options:
(a) Both Statement-I and Statement-II are correct, and Statement-II is the correct explanation for Statement-I.
(b) Both Statement-I and Statement-II are correct, but Statement-II is not the correct explanation for Statement-I.
(c) Statement-I is correct, but Statement-II is incorrect.
(d) Statement-I is incorrect, but Statement-II is correct.

Answer: C
            """
        },
        "Complex 3-Stmt Assertion-Reason": {
            "description": """
        1.  **Format:** THREE statements required: Statement-I, Statement-II, Statement-III.
        2.  **CRITICAL - ALL 3 STATEMENTS REQUIRED:**
            * Statement-I: Main assertion/claim to be analyzed
            * Statement-II: First potential explanation for Statement-I
            * Statement-III: Second potential explanation for Statement-I
            * ALL THREE must be present - DO NOT omit Statement-III
        3.  **MANDATORY OPTION FORMAT (3-STMT SPECIFIC - DIFFERENT FROM 2-STMT):**
            (a) Both Statement II and Statement III are correct and both of them explain Statement I
            (b) Both Statement II and Statement III are correct but only one of them explains Statement I
            (c) Only one of the Statements II and III is correct and that explains Statement I
            (d) Neither Statement II nor Statement III is correct
        4.  **EXACT STRUCTURE TO FOLLOW:**
            ```
            Consider the following statements:

            Statement-I: [Main assertion/claim]
            Statement-II: [First potential explanation]
            Statement-III: [Second potential explanation]

            Which one of the following is correct in respect of the above statements?
            ```
        5.  **DO NOT** use 2-statement assertion-reason option format for this pattern.
        6.  **FAILURE CONDITIONS:** Question is INVALID if: (a) Missing Statement-III, OR (b) Using 2-stmt option format.
            """,
            "example": """
Question:
Consider the following statements:

Statement-I: The Montagu-Chelmsford Reforms (1919) failed to satisfy the aspirations of Indian nationalists.
Statement-II: The Reforms introduced the system of 'Dyarchy' in the provinces, which was deemed complex and unsatisfactory.
Statement-III: The Reforms made no provision for a responsible government at the Centre and postponed the grant of 'Dominion Status'.

Which one of the following is correct in respect of the above statements?

Options:
(a) Both Statement II and Statement III are correct and both of them explain Statement I.
(b) Both Statement II and Statement III are correct but only one of them explains Statement I.
(c) Only one of the Statements II and III is correct and that explains Statement I.
(d) Neither Statement II nor Statement III is correct.

Answer: A
            """
        },
        "Chronological Ordering": {
            "description": """
        1.  **Format:** The question MUST have multiple terms, options will test chronological order knowledge of candidate. The options will be in the format of sequences and the sequence must not be 1-2-3-4. The options must be generated in such a way that the answer sequence is not always option `1-2-3-4` or any specific option. It should vary.
        2.  **CRITICAL RANDOMIZATION REQUIREMENT:**
            * **FORBIDDEN SEQUENCES:** The correct answer sequence MUST NOT be "1-2-3-4" or "4-3-2-1". These are STRICTLY PROHIBITED.
            * **MANDATORY SHUFFLING:** ALL four options MUST contain different permutations of the sequence. At least 3-4 distinct permutations must be present across options.
            * **Examples of GOOD shuffling:** "2-3-1-4", "3-1-4-2", "4-2-1-3", "1-4-2-3"
            * **Examples of BAD/FORBIDDEN:** "1-2-3-4", "4-3-2-1" (never use these as correct answer)
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Terms:** Terms must be concise and small (single word/phrase is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions challenging.
            """,
            "example": """
Question:
Arrange the following events of the Indian National Movement in their correct chronological order (earliest first):

1. Quit India Movement
2. Gandhi-Irwin Pact
3. August Offer
4. Poona Pact

Select the correct answer using the code given below:

Options:
(a) 4 - 2 - 3 - 1
(b) 2 - 4 - 3 - 1
(c) 4 - 2 - 1 - 3
(d) 2 - 4 - 1 - 3

Answer: C
            """
        },
        "Geographical Sequencing": {
            "description": """
        1.  **Format:** The question MUST have multiple Terms, options will test geographical Sequencing knowledge of candidate.
        2.  **CRITICAL RANDOMIZATION REQUIREMENT:**
            * **FORBIDDEN SEQUENCES:** The correct answer sequence MUST NOT be "1-2-3-4" or "4-3-2-1". These are STRICTLY PROHIBITED.
            * **MANDATORY SHUFFLING:** ALL four options MUST contain different permutations of the sequence. At least 3-4 distinct permutations must be present across options.
            * **Examples of GOOD shuffling:** "2-3-1-4", "3-1-4-2", "4-2-1-3", "1-4-2-3"
            * **Examples of BAD/FORBIDDEN:** "1-2-3-4", "4-3-2-1" (never use these as correct answer)
        3.  **Difficulty & Knowledge Check:** The question MUST NOT be a simple fact check or based on commonly known, basic, standard facts. It must test the candidate's:
            * **DEEP Conceptual Understanding.**
            * **High-Standard Factual Precision** (equivalent to UPSC Preliminary standards).
        4.  **Terms:** Terms must be concise and small (single word/phrase is acceptable), yet deliberately **TOUGH and CLOSELY RELATED** to make subtle distinctions challenging.
            """,
            "example": """
Question:
Consider the following cities. What is the correct sequence of their location from North to South?

1. Hyderabad
2. Nagpur
3. Bhopal
4. Chennai

Select the correct answer using the code given below:

Options:
(a) 3 - 2 - 1 - 4
(b) 2 - 3 - 1 - 4
(c) 3 - 1 - 2 - 4
(d) 2 - 1 - 3 - 4

Answer: C
            """
        }
    },
    "cognitive_types": {
        "Recall/Recognition": {
            "description": "Tests pure factual, definitional, or date-based memory. Questions check if the candidate can recognize specific, isolated pieces of information.",
            "example": "Which of the following mountain passes connects Lahaul Valley to Spiti Valley in Himachal Pradesh?"
        },
        "Comprehension/Conceptual": {
            "description": "Tests the understanding of mechanisms, core concepts, or fundamental meanings. Questions require linking cause and effect or interpreting a defined principle.",
            "example": "Which of the following is the most likely long-term consequence of the increasing tropical cyclones in the Bay of Bengal on the coastal ecology of Odisha?"
        },
        "Application/Analysis": {
            "description": "Tests the ability to apply theoretical knowledge to a scenario or analyze multiple statements for correctness. These often use 'Consider the following statements' format requiring elimination based on analytical reasoning.",
            "example": "With reference to the recent amendments to the Insolvency and Bankruptcy Code (IBC), consider Statement 1 and Statement 2..."
        },
        "Higher Reasoning/Synthesis": {
            "description": "Tests multi-domain, multi-step reasoning, or synthesis of complex data/concepts across different subjects (e.g., economics and environment). These demand high-level judgment and integration.",
            "example": "Which of the following is the most appropriate reason for the simultaneous rise in both inflation and unemployment observed in some developing economies?"
        }
    },
    "difficulty_levels": {
        "Easy": "Straightforward questions testing basic concepts or facts.",
        "Moderate": "Questions requiring connection of multiple concepts or elimination of close distractors.",
        "Difficult": "Questions testing obscure facts, complex inter-disciplinary linkages, or very subtle distinctions."
    }
}
