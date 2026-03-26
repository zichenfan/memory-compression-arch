import time
from typing import List, Dict

# 模拟的 Agent 基础类
class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def log(self, msg: str):
        print(f"[{self.name} - {self.role}] {msg}")

    def execute_task(self, task: str, context: Dict) -> Dict:
        raise NotImplementedError

# 1. 项目经理 Agent
class ManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Jason-PM", "Project Manager")

    def execute_task(self, task: str, context: Dict) -> Dict:
        self.log(f"Received high-level task: {task}")
        self.log("Breaking down into sub-tasks...")
        time.sleep(1)
        sub_tasks = [
            {"type": "code", "desc": f"Implement core logic for: {task}"},
            {"type": "test", "desc": f"Write and run unit tests for: {task}"}
        ]
        return {"sub_tasks": sub_tasks}

# 2. 程序员 Agent
class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__("OpenClaw-Coder", "Software Engineer")

    def execute_task(self, task: str, context: Dict) -> Dict:
        self.log(f"Writing code for: {task}")
        time.sleep(2) # 模拟思考和写代码的时间
        
        # 模拟生成代码
        mock_code = f"""
def bdi_compress(cache_line):
    # Simulated {task}
    base = cache_line[0]
    deltas = [val - base for val in cache_line]
    return deltas
"""
        self.log("Code generation completed.")
        return {"code": mock_code, "status": "success"}

# 3. 测试与审查 Agent
class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__("OpenClaw-Reviewer", "QA Engineer")

    def execute_task(self, task: str, context: Dict) -> Dict:
        code_to_test = context.get("code", "")
        self.log(f"Reviewing and testing the following code:\n{code_to_test}")
        time.sleep(1.5)
        
        # 模拟 80% 的概率通过，20% 的概率打回
        import random
        if random.random() > 0.2:
            self.log("All tests passed! LGTM 👍")
            return {"status": "passed", "feedback": "Looks good"}
        else:
            self.log("Tests failed! Found an edge case with zero values.")
            return {"status": "failed", "feedback": "Fix zero value handling"}

# ==========================================
# 核心协同控制器 (The Orchestrator)
# ==========================================
class MultiAgentOrchestrator:
    def __init__(self):
        self.pm = ManagerAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()

    def run_workflow(self, project_goal: str):
        print(f"\n🚀 Starting Multi-Agent Workflow for Goal: '{project_goal}'\n")
        
        # Phase 1: 经理拆解任务
        pm_result = self.pm.execute_task(project_goal, {})
        sub_tasks = pm_result["sub_tasks"]
        
        code_context = {}
        
        # Phase 2 & 3: 程序员和测试员的协同循环
        max_retries = 3
        for task in sub_tasks:
            if task["type"] == "code":
                # 程序员开始写代码
                coder_result = self.coder.execute_task(task["desc"], {})
                code_context["code"] = coder_result["code"]
                
            elif task["type"] == "test":
                # 测试员审查，如果失败则循环打回
                for attempt in range(max_retries):
                    review_result = self.reviewer.execute_task(task["desc"], code_context)
                    
                    if review_result["status"] == "passed":
                        break
                    else:
                        print(f"\n⚠️ Review failed. Sending feedback back to Coder (Attempt {attempt+1}/{max_retries})...")
                        # 再次调用程序员修复
                        fix_task = f"Fix bug based on feedback: {review_result['feedback']}"
                        coder_result = self.coder.execute_task(fix_task, code_context)
                        code_context["code"] = coder_result["code"] # 更新代码
                
                if review_result["status"] != "passed":
                    print("\n❌ Workflow failed. Max retries reached for fixing code.")
                    return

        print("\n✅ Multi-Agent Workflow Completed Successfully!")
        print("\n=== Final Deliverable ===")
        print(code_context["code"])

if __name__ == "__main__":
    orchestrator = MultiAgentOrchestrator()
    orchestrator.run_workflow("Implement BDI Memory Compression Algorithm")
