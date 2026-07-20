"""陪练开场白模板（LLM 不可用时的降级首句）。"""

from __future__ import annotations

from typing import Optional

from leetcode_tracker.kg.queries import NodePlacement


def _status_hint(status: str) -> str:
    if status == "Wrong Answer":
        return "这次 Wrong Answer"
    if status == "Time Limit Exceeded":
        return "超时了"
    if status == "Compile Error":
        return "编译没通过"
    if status == "Runtime Error":
        return "运行出错了"
    return f"结果是 {status}"


def template_opening(
    *,
    problem_id: int,
    title: str,
    status: str,
    placement: Optional[NodePlacement],
    today_count: int,
) -> str:
    label = f"{problem_id}. {title}"
    if today_count > 1:
        label += f"（今天第 {today_count} 次提交）"

    # AC：极简方向锁定，不给模型「卡点」语感
    if status == "Accepted":
        return (
            f"✅ {label} 已通过。"
            "接下来想聊优化方向——你更关注耗时、内存，还是代码可读性？"
        )

    hint = _status_hint(status)
    head = f"{hint}：{label}"

    if placement is None:
        return (
            f"{head}。这道题不在学习路线图里——"
            "先说说你卡在哪，或打算怎么验证自己的想法？"
        )

    module = f"{placement.track_name} / {placement.submodule_name}"
    progress = f"{placement.accepted_in_node}/{placement.total_in_node}"
    ann = f"，考点标注：{placement.annotation}" if placement.annotation else ""
    return (
        f"{head}。属于路线 {module} 第 {placement.sort_order} 题{ann}，"
        f"子模块进度 {progress}。"
        "你最先怀疑的是边界、复杂度，还是实现细节？"
    )
