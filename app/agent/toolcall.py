import asyncio
import json
from typing import Any, List, Optional, Union

from pydantic import Field

from app.agent.react import ReActAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, ToolCall, ToolChoice
from app.tool import CreateChatCompletion, Terminate, ToolCollection


TOOL_CALL_REQUIRED = "Tool calls required but none provided"


def _parse_tool_arguments(raw_arguments: str | None) -> dict[str, Any]:
    """解析工具参数；必要时修复对象内误写的裸字符串条目。"""
    raw = raw_arguments or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as original_error:
        repaired = _repair_unkeyed_object_strings(raw)
        if repaired != raw:
            try:
                logger.warning("工具参数不是严格 JSON，已尝试修复对象内裸字符串条目后继续执行。")
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        raise original_error


def _repair_unkeyed_object_strings(raw: str) -> str:
    """把 {"事实", "键": "值"} 修复为 {"_item_1": "事实", "键": "值"}。"""
    output: list[str] = []
    stack: list[str] = []
    item_counts: list[int] = []
    previous_significant = ""
    index = 0

    while index < len(raw):
        char = raw[index]
        if char == '"':
            token, index = _read_json_string_token(raw, index)
            next_significant = _peek_next_significant(raw, index)
            if (
                stack
                and stack[-1] == "object"
                and previous_significant in {"{", ","}
                and next_significant in {",", "}"}
            ):
                item_counts[-1] += 1
                output.append(f'"_item_{item_counts[-1]}": ')
            output.append(token)
            previous_significant = '"'
            continue

        output.append(char)
        if char == "{":
            stack.append("object")
            item_counts.append(0)
            previous_significant = char
        elif char == "[":
            stack.append("array")
            item_counts.append(0)
            previous_significant = char
        elif char in {"}", "]"}:
            if stack:
                stack.pop()
                item_counts.pop()
            previous_significant = char
        elif not char.isspace():
            previous_significant = char
        index += 1

    return "".join(output)


def _read_json_string_token(raw: str, start: int) -> tuple[str, int]:
    escaped = False
    index = start + 1
    while index < len(raw):
        char = raw[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return raw[start : index + 1], index + 1
        index += 1
    return raw[start:], len(raw)


def _peek_next_significant(raw: str, start: int) -> str:
    index = start
    while index < len(raw) and raw[index].isspace():
        index += 1
    return raw[index] if index < len(raw) else ""


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    _current_base64_image: Optional[str] = None

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    # 工具返回的 ToolResult.system 数据通道（Bug1）。
    # 上一轮 act() 的工具把全量数据（如 python stdout）放进 system，
    # 下一轮 think() 注入为 system message，不受 max_observe 截断，
    # 模型可直接基于完整数据回答，无需复述被截断的 observation。
    pending_systems: List[str] = Field(default_factory=list)

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        # 组装 system messages：系统提示词 + 上一轮工具收集的 system 数据
        system_msgs: list[Message] = []
        if self.system_prompt:
            system_msgs.append(Message.system_message(self.system_prompt))
        if self.pending_systems:
            system_msgs.append(
                Message.system_message(
                    "# 工具返回的完整数据（请直接据此回答，不要复述原始内容）\n"
                    "# 若下方数据出现截断标记，说明输出超长已截断，请勿基于残缺数据下结论，"
                    "应精简脚本只打印统计结果后重跑。\n" + "\n\n".join(self.pending_systems)
                )
            )
            self.pending_systems = []

        try:
            # Get response with tool options
            response = await self.llm.ask_tool(
                messages=self.messages,
                system_msgs=(system_msgs if system_msgs else None),
                tools=self.available_tools.to_params(),
                tool_choice=self.tool_choices,
            )
        except ValueError:
            raise
        except Exception as e:
            # Check if this is a RetryError containing TokenLimitExceeded
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(
                    f"🚨 Token limit error (from RetryError): {token_limit_error}"
                )
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum token limit reached, cannot continue execution: {str(token_limit_error)}"
                    )
                )
                self.state = AgentState.FINISHED
                return False
            raise

        self.tool_calls = tool_calls = (
            response.tool_calls if response and response.tool_calls else []
        )
        content = response.content if response and response.content else ""

        # Log response info
        logger.info(f"✨ {self.name}'s thoughts: {content}")
        logger.info(
            f"🛠️ {self.name} selected {len(tool_calls) if tool_calls else 0} tools to use"
        )
        if tool_calls:
            logger.info(
                f"🧰 Tools being prepared: {[call.function.name for call in tool_calls]}"
            )
            logger.info(f"🔧 Tool arguments: {tool_calls[0].function.arguments}")

        try:
            if response is None:
                raise RuntimeError("No response received from the LLM")

            # Handle different tool_choices modes
            if self.tool_choices == ToolChoice.NONE:
                if tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if content:
                    self.memory.add_message(Message.assistant_message(content))
                    return True
                return False

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls
                else Message.assistant_message(content)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == ToolChoice.REQUIRED and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, if no tool calls but content exists,
            # the model chose to respond with text — mark as finished
            if self.tool_choices == ToolChoice.AUTO and not self.tool_calls:
                if content:
                    self.state = AgentState.FINISHED
                return False

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        results = []
        for command in self.tool_calls:
            # Reset base64_image for each tool call
            self._current_base64_image = None

            result = await self.execute_tool(command)

            if self.max_observe:
                result = result[: self.max_observe]

            logger.info(
                f"🎯 Tool '{command.function.name}' completed its mission! Result: {result}"
            )

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
                base64_image=self._current_base64_image,
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = _parse_tool_arguments(command.function.arguments)

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)

            # 收集 ToolResult.system（全量数据通道，Bug1）
            # 模型在下一轮 think() 以 system message 形式收到，不受 max_observe 截断
            system_data = getattr(result, "system", None)
            if system_data:
                self.pending_systems.append(str(system_data))

            # Handle special tools
            await self._handle_special_tool(name=name, result=result)

            # Check if result is a ToolResult with base64_image
            if hasattr(result, "base64_image") and result.base64_image:
                # Store the base64_image for later use in tool_message
                self._current_base64_image = result.base64_image

            # Format result for display (standard case)
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

    async def cleanup(self):
        """Clean up resources used by the agent's tools."""
        logger.info(f"🧹 Cleaning up resources for agent '{self.name}'...")
        for tool_name, tool_instance in self.available_tools.tool_map.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                tool_instance.cleanup
            ):
                try:
                    logger.debug(f"🧼 Cleaning up tool: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    logger.error(
                        f"🚨 Error cleaning up tool '{tool_name}': {e}", exc_info=True
                    )
        logger.info(f"✨ Cleanup complete for agent '{self.name}'.")

    async def run(self, request: Optional[str] = None) -> str:
        """Run the agent with cleanup when done."""
        try:
            return await super().run(request)
        finally:
            await self.cleanup()
