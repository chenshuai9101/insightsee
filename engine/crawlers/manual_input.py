"""手动输入适配器 - 用户 Web UI 粘贴的数据直接转换为 RawItem"""

from datetime import datetime
from typing import Optional

from engine.analyzers.models import RawItem


class ManualInputAdapter:
    """手动输入适配器"""

    platform = "manual"

    def search(self, keyword: str, limit: int = 20) -> list[RawItem]:
        """手动模式不支持搜索"""
        return []

    def get_comments(self, target_id: str, limit: int = 50) -> list[RawItem]:
        return []

    @staticmethod
    def from_text(
        text: str,
        source: str = "unknown",
        author: str = "用户",
        title: str = "",
    ) -> RawItem:
        """将一段手动输入的文本转换为 RawItem

        Args:
            text: 用户粘贴的抱怨/反馈文本
            source: 来源平台标识 (weibo/zhihu/xiaohongshu/manual 等)
            author: 作者名
            title: 标题
        """
        return RawItem(
            platform=source if source else "manual",
            content=text.strip(),
            author=author,
            title=title or text.strip()[:50],
            url="",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    @staticmethod
    def from_batch(
        texts: list[str],
        source: str = "manual",
    ) -> list[RawItem]:
        """批量转换"""
        return [
            RawItem(
                platform=source,
                content=t.strip(),
                author="用户",
                title=t.strip()[:50],
                url="",
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            for t in texts
            if t.strip()
        ]


class MockDataGenerator:
    """测试数据生成器"""

    @staticmethod
    def generate_product_complaints() -> list[RawItem]:
        """生成产品抱怨测试数据"""
        now = datetime.now()
        data = [
            ("手机才用三天就自动关机了，垃圾产品！", "weibo", "小明"),
            ("这破路由器信号差得要命，隔一堵墙就没网了", "zhihu", "匿名用户"),
            ("客服态度极差，问三句回一句，还怼人", "weibo", "小张"),
            ("物流慢得离谱，说好三天到结果一周", "taobao", "买家123"),
            ("价格比隔壁贵了30%，质量还一样，坑", "xiaohongshu", "省钱小能手"),
            ("买了不到一个月就坏了，售后还推诿", "taobao", "老用户"),
            ("App 频繁闪退，更新后更卡了，负优化", "zhihu", "技术控"),
            ("包装破损严重，明显是二手翻新货", "weibo", "维权中"),
            ("虚假宣传，实物和图片完全不一样", "xiaohongshu", "踩雷专业户"),
            ("预约了三天都没人来修，服务太差", "weibo", "愤怒的顾客"),
            ("质量越来越差了，老用户真的很失望", "taobao", "忠实粉丝"),
            ("界面改版后丑到爆，还找不到功能在哪", "zhihu", "保守派"),
        ]
        items = []
        for i, (text, platform, author) in enumerate(data):
            items.append(RawItem(
                platform=platform,
                content=text,
                author=author,
                title=text[:50],
                url="",
                created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            ))
        return items

    @staticmethod
    def generate_service_complaints() -> list[RawItem]:
        """生服务抱怨测试数据"""
        data = [
            ("客服电话打了一个小时没人接", "weibo", "打工人"),
            ("退款申请提交一周还在审核中", "taobao", "买家"),
            ("安装师傅态度恶劣，还索要小费", "weibo", "新房主"),
            ("会员自动续费找不到关闭入口", "zhihu", "用户"),
            ("投诉后不但没解决还被拉黑了", "weibo", "伤心人"),
        ]
        now = datetime.now()
        return [
            RawItem(platform=p, content=t, author=a, title=t[:50], url="",
                    created_at=now.strftime("%Y-%m-%d %H:%M:%S"))
            for t, p, a in data
        ]


# =========================== 测试 ===========================
if __name__ == "__main__":
    print("=== ManualInputAdapter 测试 ===")
    item = ManualInputAdapter.from_text("这个产品太难用了，设计不合理", source="weibo")
    print(f"  platform={item.platform}, content={item.content}, author={item.author}")

    batch = ManualInputAdapter.from_batch(["差评1", "差评2", "差评3"], source="taobao")
    print(f"  batch: {len(batch)} items")

    print("\n=== MockDataGenerator 测试 ===")
    items = MockDataGenerator.generate_product_complaints()
    print(f"  生成了 {len(items)} 条测试数据:")
    for item in items[:3]:
        print(f"    [{item.platform}] {item.content[:40]}... @{item.author}")
