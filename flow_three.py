from typing import Optional

from anthropic import Anthropic

from lib.anthropic_interactions.queries import classify_job_query, extract_skills_from_job_query, \
    extract_title_from_contact_query
from lib.anthropic_interactions.tools import classify_job_tool, extract_skills_from_job_tool, extract_title_tool
from pydantic_schemas.AnthropicSanitizerError import AnthropicSanitizerError
from shared.settings import ANTHROPIC_API_KEY, ANTHROPIC_HAIKU, ANTHROPIC_SONNET
from shared.logger import logger
from shared.utils import join_values_into_strings


class AnthropicWrapper:
    API = Anthropic(api_key=ANTHROPIC_API_KEY)

    @staticmethod
    def use_tool(query: str, tool: dict, model: str, max_tokens: int) -> dict:
        """
        The query needs to contain "Use the `<tool_name> tool`

        Returns:
        {
            "result": the dict with the tool output on success OR None on error,
            "error": an error message on error OR None on success
        """
        try:
            response = AnthropicWrapper.API.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                tools=[tool],
                messages=[{"role": "user", "content": query}]
            )

            if response.stop_reason is not None and response.stop_reason == "max_tokens":
                logger.error(join_values_into_strings(
                    "Tool usage went over max tokens. Tool name: ",
                    tool.get("name"),
                    " Max tokens: ",
                    max_tokens,
                ))

        except Exception as e:
            return {
                "result": None,
                "error": str(e)
            }

        json_summary = {}
        for content in response.content:
            if content.type == "tool_use" and content.name == tool.get("name"):
                json_summary = content.input
                break

        if len(json_summary) > 0:
            return {
                "result": json_summary,
                "error": None
            }
        else:
            return {
                "result": None,
                "error": "No tool output found"
            }

    @staticmethod
    def check_high_quality_job(job_description: str, job_uid: str) -> tuple[bool, dict]:
        tool_use_dict = AnthropicWrapper.use_tool(
            query=classify_job_query.format(job_description=job_description),
            tool=classify_job_tool,
            model=ANTHROPIC_SONNET,
            max_tokens=400
        )

        acceptable_roles = classify_job_tool["input_schema"]["properties"]["role"]["enum"]

        if tool_use_dict["error"] is not None:
            logger.error(join_values_into_strings(
                "Error checking job quality: ",
                tool_use_dict["error"]
            ))
            return False, {}
        else:
            verdict = True

            structured_response = tool_use_dict["result"]

            if not structured_response:
                verdict = False

            job_completeness = structured_response["job_completeness_score"] if "job_completeness_score" in structured_response else 0
            if job_completeness < 80:
                verdict = False

            role = structured_response["role"] if "role" in structured_response else "Other IT role"
            role = role if role in acceptable_roles else "Other IT role"

            if role == "Other IT role":
                verdict = False

            university_or_public_institution = True
            if "university_or_public_institution_job" in structured_response:
                university_or_public_institution = structured_response["university_or_public_institution_job"]

            if university_or_public_institution is True:
                verdict = False

            if verdict is False:
                logger.error(join_values_into_strings(
                    "Job with UID ",
                    job_uid,
                    " has been classified as a low-quality job with a score of ",
                    job_completeness,
                    " result dict is: ",
                    structured_response
                ))
            else:
                logger.info(join_values_into_strings(
                    "Job with UID ",
                    job_uid,
                    " has been classified as a high-quality job with a score of ",
                    job_completeness,
                ))

            return verdict, structured_response

    @staticmethod
    def extract_title_from_contact(contact_info: str) -> Optional[str]:
        tool_use_dict = AnthropicWrapper.use_tool(
            query=extract_title_from_contact_query.format(contact_info=contact_info),
            tool=extract_title_tool,
            model=ANTHROPIC_SONNET,
            max_tokens=400
        )

        if tool_use_dict["error"] is not None:
            logger.error(join_values_into_strings(
                "Error extracting title category: ",
                tool_use_dict["error"]
            ))
            return None

        if tool_use_dict["result"].get("title_category") is None:
            logger.error(join_values_into_strings(
                "Error extracting title category: ",
                "No title category found"
            ))
            return None

        return tool_use_dict["result"]["title_category"]

    @staticmethod
    def extract_skills_from_job_description(job_description: str) -> dict:
        """

        Args:
            job_description: str

        Returns:
            {
                "core_technical_skills": list[str],
                "supporting_technical_skills" : list[str],
                "other_technical_skills": list[str],
            }
        """

        tool_use_dict = AnthropicWrapper.use_tool(
            query=extract_skills_from_job_query.format(job_description=job_description),
            tool=extract_skills_from_job_tool,
            model=ANTHROPIC_HAIKU,
            max_tokens=400,
        )

        if tool_use_dict["error"] is not None:
            logger.error(join_values_into_strings(
                "Error extracting skills from job description: ",
                tool_use_dict["error"]
            ))

            return {}

        if tool_use_dict.get("result") is None:
            logger.error(join_values_into_strings(
                "Error extracting skills from job description: ",
                "No results"
            ))
            return {}

        res = tool_use_dict["result"]
        if res.get("core_technical_skills") is None:
            res["core_technical_skills"] = []

        if res.get("supporting_technical_skills") is None:
            res["supporting_technical_skills"] = []

        if res.get("other_technical_skills") is None:
            res["other_technical_skills"] = []

        return res

    @staticmethod
    def sanitise_job_description(job_description: str) -> tuple[str, None] | tuple[None, AnthropicSanitizerError]:
        try:
            query = f""" I want to clean the job description posted above of any sensitive data that may allow an 
            applicant that gets a hold of it to apply directly to the job board or job website instead of using my 
            hiring platform. 

            Remove any company names and replace them with a neutral placeholder where possible so the original 
            meaning and sentence structure is maintained. 
            Here is an example: 
            IndexDev is a recruitment platform aimed at…. should be rewritten as 
            Our company is a recruitment platform aimed at…

            Remove any salary estimates, be they hourly, daily, monthly or yearly estimates. 
            Here is an example: 
            Annual salary for this position is within 70-80k USD should be completely removed. 

            Remove any direct speech from the recruiter or info that may include the recruiter and replace them so the 
            original meaning and sentence structure is maintained. 

            Remove any first person point-of-view speech, names, titles. Modify the information so that it is written on 
            behalf of the company instead. 
            Here is an example: 
            I am Maxim, tech recruiter for IndexDev, and we are looking for a backend Ruby dev should be replaced with 
            Our company is looking for a backend Ruby dev. 

            Remove any external contact information: emails, phone numbers. 
            Here is an example: You can contact IndexDev by phone: +37813374269 or email: index@dev.com should be 
            completely removed. 

            Remove any addresses. 
            Here is an example: Chisinau, Stefan cel Mare blvd, 135 should be completely removed. 

            Remove any URLs. 
            Here is an example: You can apply via this link: https://linktosomething.com/something-external should be 
            completely removed. 

            Replace any occurrences of key: value pairs as instructed:
            If the occurrence is of the format "Remote Job: <True/False>", replace it with 
            "This is a remote opportunity" or "This is not a remote opportunity" appropriately. 
            If "Location: Anywhere" is found later in the job description, remove it completely.
            If the occurrence is of the format "Location: <Where>", replace it with "This is a/an <Where> based job 
            opportunity. Make sure to replace "<Where>" with the actual location. 
            If the occurrence is of the format "Position: <Position>", remove it completely.

            Answer only with my original text after all processing, replacement and removal is complete.
            Your answer should NOT include any additional information or suggestions.


            Here is the job description I want you to sanitise:
            {job_description}
            """

            response = AnthropicWrapper.API.messages.create(
                model=ANTHROPIC_SONNET,
                max_tokens=1000,
                messages=[{"role": "user", "content": query}],
                temperature=0,
            )

            sanitised = ""
            for content_entry in response.content:
                if content_entry.type == "text":
                    sanitised = content_entry.text
                    break

            return sanitised, None
        except Exception as e:
            return None, AnthropicSanitizerError(error=str(e))
