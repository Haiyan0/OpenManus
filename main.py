import entry

entry.apply_env(entry.parse_env())  # 必须先于 app.* import：config 单例在首次 import 时加载

import argparse  # noqa: E402
import asyncio  # noqa: E402

from app.agent.manus import Manus  # noqa: E402
from app.logger import logger  # noqa: E402


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument(
        "env",
        nargs="?",
        default=None,
        help="部署环境：dev（默认）或 test，选择 config/config_{env}.toml",
    )
    parser.add_argument(
        "--prompt", type=str, required=False, help="Input prompt for the agent"
    )
    args = parser.parse_args()

    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        # Use command line prompt if provided, otherwise ask for input
        prompt = args.prompt if args.prompt else input("Enter your prompt: ")
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
