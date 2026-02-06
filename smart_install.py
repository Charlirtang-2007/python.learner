
"""
智能包安装工具 - 自动使用国内镜像源
"""

import subprocess
import sys
import time
import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
class SmartInstaller:
    def __init__(self):
        # 国内常用镜像源
        self.mirrors = {
            '清华': 'https://pypi.tuna.tsinghua.edu.cn/simple',
            '阿里云': 'https://mirrors.aliyun.com/pypi/simple',
            '腾讯云': 'https://mirrors.cloud.tencent.com/pypi/simple',
            '华为云': 'https://repo.huaweicloud.com/repository/pypi/simple',
            '豆瓣': 'https://pypi.douban.com/simple',
            '中科大': 'https://pypi.mirrors.ustc.edu.cn/simple',
            '网易': 'https://mirrors.163.com/pypi/simple',
            '官方源': 'https://pypi.org/simple'
        }

        # 默认选中的镜像源（按优先级排序）
        self.default_mirrors = ['清华', '阿里云', '腾讯云', '豆瓣']

    def test_mirror_speed(self, mirror_name, mirror_url):
        """测试镜像源响应速度"""
        try:
            start_time = time.time()
            # 测试镜像源根域名（去掉/simple）
            test_url = mirror_url.replace('/simple', '')
            if not test_url.endswith('/'):
                test_url += '/'

            # 设置超时和重试
            response = requests.get(test_url, timeout=3)
            response_time = (time.time() - start_time) * 1000  # 毫秒

            if response.status_code == 200:
                return mirror_name, mirror_url, response_time, True
            else:
                return mirror_name, mirror_url, float('inf'), False
        except Exception as e:
            print(f"  镜像源 {mirror_name} 测试失败: {str(e)[:50]}...")
            return mirror_name, mirror_url, float('inf'), False

    def find_fastest_mirror(self, manual_mirror=None):
        """寻找最快的镜像源"""
        if manual_mirror and manual_mirror in self.mirrors:
            print(f"🔧 使用指定镜像源: {manual_mirror}")
            return manual_mirror, self.mirrors[manual_mirror]

        print("🔍 正在测试镜像源速度...")

        results = []
        with ThreadPoolExecutor(max_workers=len(self.default_mirrors)) as executor:
            # 提交所有测试任务
            future_to_mirror = {
                executor.submit(
                    self.test_mirror_speed,
                    name,
                    self.mirrors[name]
                ): name for name in self.default_mirrors
            }

            # 收集结果
            for future in as_completed(future_to_mirror):
                name, url, speed, success = future.result()
                if success:
                    results.append((name, url, speed))
                    print(f"  ✓ {name}: {speed:.0f}ms")
                else:
                    print(f"  ✗ {name}: 不可用")

        if not results:
            print("⚠️  所有镜像源都不可用，使用官方源")
            return '官方源', self.mirrors['官方源']

        # 按速度排序
        results.sort(key=lambda x: x[2])
        fastest = results[0]
        print(f"\n🚀 选择最快镜像源: {fastest[0]} ({fastest[2]:.0f}ms)")
        return fastest[0], fastest[1]

    def build_pip_command(self, mirror_url, package_name=None, upgrade=False, requirements_file=None):
        """构建pip命令"""
        pip_cmd = [sys.executable, '-m', 'pip', 'install']

        if upgrade:
            pip_cmd.append('--upgrade')

        # 添加镜像源
        mirror_host = mirror_url.split('//')[1].split('/')[0]
        pip_cmd.extend(['-i', mirror_url, '--trusted-host', mirror_host])

        # 添加包名或requirements文件
        if requirements_file:
            pip_cmd.extend(['-r', requirements_file])
        elif package_name:
            pip_cmd.append(package_name)

        return pip_cmd

    def install_package(self, package_name=None, upgrade=False, requirements_file=None, mirror=None):
        """安装包"""
        # 查找最快镜像源
        mirror_name, mirror_url = self.find_fastest_mirror(mirror)

        if requirements_file:
            print(f"\n📦 从 {requirements_file} 安装依赖包...")
        else:
            print(f"\n📦 安装包: {package_name}...")

        print(f"🌐 使用镜像: {mirror_name} ({mirror_url})")

        # 构建pip命令
        pip_cmd = self.build_pip_command(mirror_url, package_name, upgrade, requirements_file)
        print(f"🔧 执行命令: {' '.join(pip_cmd)}\n")

        # 执行安装
        try:
            result = subprocess.run(pip_cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            print("✅ 安装成功！")
            if result.stdout:
                print(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            print("❌ 安装失败！")
            if e.stderr:
                print(f"错误信息:\n{e.stderr}")

            # 尝试使用备用镜像源
            print("\n🔄 尝试使用备用镜像源...")
            for name, url in self.mirrors.items():
                if name != mirror_name:
                    print(f"  尝试: {name}")
                    pip_cmd = self.build_pip_command(url, package_name, upgrade, requirements_file)
                    try:
                        subprocess.run(pip_cmd, check=True)
                        print(f"✅ 使用 {name} 安装成功！")
                        return True
                    except:
                        continue

            print("💥 所有镜像源都失败，请检查网络或包名")
            return False

    def list_installed_packages(self):
        """列出已安装的包"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            print("📋 已安装的包:")
            print(result.stdout)
        except Exception as e:
            print(f"❌ 无法列出包: {e}")

    def set_persistent_mirror(self, mirror_name=None):
        """永久设置镜像源"""
        if mirror_name and mirror_name in self.mirrors:
            mirror_url = self.mirrors[mirror_name]
        else:
            mirror_name, mirror_url = self.find_fastest_mirror()

        print(f"\n🔧 永久设置为: {mirror_name}")
        print(f"   镜像地址: {mirror_url}")

        # 创建pip配置文件内容
        mirror_host = mirror_url.split('//')[1].split('/')[0]
        config_content = f"""[global]
index-url = {mirror_url}
trusted-host = {mirror_host}
timeout = 6000

[install]
trusted-host = {mirror_host}
"""

        # 确定配置文件路径
        import platform

        if platform.system() == 'Windows':
            pip_dir = os.path.join(os.environ.get('APPDATA', ''), 'pip')
            config_file = os.path.join(pip_dir, 'pip.ini')
        else:
            pip_dir = os.path.join(os.path.expanduser('~'), '.pip')
            config_file = os.path.join(pip_dir, 'pip.conf')

        os.makedirs(pip_dir, exist_ok=True)

        try:
            # 备份原有配置
            if os.path.exists(config_file):
                backup_file = config_file + '.backup'
                with open(config_file, 'r', encoding='utf-8') as f:
                    with open(backup_file, 'w', encoding='utf-8') as bf:
                        bf.write(f.read())
                print(f"📂 原有配置已备份到: {backup_file}")

            # 写入新配置
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_content)

            print(f"✅ 配置文件已保存到: {config_file}")
            print("🎯 以后使用 `pip install` 将自动使用此镜像源")
            return True
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
            return False


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 Python 智能包安装工具 v2.0")
    print("=" * 50)

    installer = SmartInstaller()

    if len(sys.argv) < 2:
        print("\n📖 使用方法:")
        print("  安装包: python smart_install.py <包名1> <包名2> ...")
        print("  升级包: python smart_install.py --upgrade <包名>")
        print("  指定镜像: python smart_install.py --mirror 清华 <包名>")
        print("  从文件安装: python smart_install.py -r requirements.txt")
        print("  列出已安装包: python smart_install.py --list")
        print("  设置永久镜像源: python smart_install.py --set-mirror [镜像名]")
        print("  测试镜像源速度: python smart_install.py --test")
        print("\n🎯 示例:")
        print("  python smart_install.py requests pandas numpy")
        print("  python smart_install.py --mirror 阿里云 requests")
        print("  python smart_install.py --upgrade pip")
        print("  python smart_install.py -r requirements.txt")
        print("  python smart_install.py --set-mirror 清华")
        return

    # 处理命令行参数
    args = sys.argv[1:]
    i = 0

    # 解析参数
    upgrade = False
    mirror = None
    requirements_file = None

    while i < len(args):
        arg = args[i]

        if arg == '--list':
            installer.list_installed_packages()
            return
        elif arg == '--set-mirror':
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                installer.set_persistent_mirror(args[i + 1])
                i += 1
            else:
                installer.set_persistent_mirror()
            return
        elif arg == '--test':
            installer.find_fastest_mirror()
            return
        elif arg == '--upgrade':
            upgrade = True
        elif arg == '--mirror':
            if i + 1 < len(args):
                mirror = args[i + 1]
                i += 1
        elif arg == '-r':
            if i + 1 < len(args):
                requirements_file = args[i + 1]
                i += 1
                # 从文件安装
                installer.install_package(
                    upgrade=upgrade,
                    requirements_file=requirements_file,
                    mirror=mirror
                )
                return
        elif not arg.startswith('-'):
            # 安装包
            package = arg
            # 检查是否还有更多包
            packages = [arg]
            i += 1
            while i < len(args) and not args[i].startswith('-'):
                packages.append(args[i])
                i += 1

            # 安装所有包
            for pkg in packages:
                installer.install_package(
                    package_name=pkg,
                    upgrade=upgrade,
                    mirror=mirror
                )
            return

        i += 1

    print("❌ 参数错误！请检查输入")
    print("💡 使用不带参数的命令查看帮助")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断操作")
    except Exception as e:
        print(f"\n💥 程序出错: {e}")
        print("💡 请检查网络连接或Python环境")