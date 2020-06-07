from importlib_resources import files

from .parsing import test_ancestry
from .parsing import level_json
from .parsing import parse_spec
from .parsing import name_from_map
from .parsing import get_non_merges
from .parsing import name_merges

from .user_messages import print_user_message
from .user_messages import show_level_name
from .user_messages import print_goal
from .user_messages import simulate_goal
from .user_messages import show_tree
from .user_messages import default_fail
from .user_messages import level_complete
from .user_messages import skill_complete
from .user_messages import all_levels_complete


class Level:
    def __init__(self, name):
        self.name = name
        self.skill = None
        self.next_level = None
        self.prev_level = None

    def __repr__(self):
        return "<{class_name}: '{full_name}'>".format(
            class_name=type(self).__name__,
            full_name=self.full_name()
        )

    def full_name(self):
        return '{} {}'.format(self.skill.name, self.name)

    def _setup(self, file_operator):
        pass

    def setup(self, file_operator):
        # Clear remotes
        level_repo = file_operator.repo
        for remote in level_repo.remotes:
            level_repo.delete_remote(remote)

        file_operator.clear_tracked_commits()

        show_level_name(self)
        self._setup(file_operator)
        self.post_setup()

        file_operator.write_level(self)

    def post_setup(self):
        pass

    def instructions(self):
        pass

    def goal(self):
        pass

    def status(self):
        show_level_name(self)

    def _test(self, file_operator):
        raise NotImplementedError

    def test(self, file_operator):
        if self._test(file_operator):
            self.test_passed()
        else:
            self.test_failed()

    def test_passed(self):
        if self.next_level is None:
            all_levels_complete()
        elif self.next_level.skill != self.skill:
            skill_complete(self)
        else:
            level_complete(self)

    def test_failed(self):
        default_fail()


class BasicLevel(Level):
    def __init__(self, name, skill_package):
        super().__init__(name)

        self.level_dir = files(skill_package).joinpath('_{}/'.format(name))

        self.setup_spec_path = self.level_dir.joinpath('setup.spec')
        self.test_spec_path = self.level_dir.joinpath('test.spec')
        self.passed_path = self.level_dir.joinpath('passed.txt')

        self.goal_path = self.level_dir.joinpath('goal.txt')
        self.instructions_path = self.level_dir.joinpath('instructions.txt')
        if not self.instructions_path.exists():
            self.instructions_path = self.goal_path

    def _setup(self, file_operator):
        commits, head = parse_spec(self.setup_spec_path)
        file_operator.create_tree(commits, head)

        latest_commit = '0'
        for commit_name, _, _, _ in commits:
            try:
                if int(commit_name) > int(latest_commit):
                    latest_commit = commit_name
            except ValueError:
                pass  # Commit is merge and doesn't have number

        file_operator.write_last_commit(latest_commit)

    def post_setup(self):
        simulate_goal(self)
        show_tree()

    def instructions(self):
        for line in self.instructions_path.read_text().strip().split('\n'):
            if line[:3] == '>>>':
                input('>>>')
            else:
                print(line.strip())

    def goal_str(self):
        return self.goal_path.read_text().strip()

    def goal(self):
        print_goal(self)

    def _test(self, file_operator):
        commits, head = parse_spec(self.test_spec_path)

        # Get commit trees
        test_tree = level_json(commits, head)
        level_tree = file_operator.get_current_tree()

        # Get commit info
        non_merges = get_non_merges(level_tree)

        # Name known commits
        known_commits = file_operator.get_known_commits()
        name_from_map(level_tree, known_commits)

        # Name rebases and cherrypicks
        known_non_merges = {commit_hash: name
                            for commit_hash, name in known_commits.items()
                            if name[:1] != 'M'}
        diff_map = file_operator.get_copy_mapping(non_merges, known_non_merges)
        name_from_map(level_tree, diff_map)

        # Name merges
        name_merges(level_tree, test_tree)

        # Test for similarity
        return test_ancestry(level_tree, test_tree)

    def test_passed(self):
        if self.passed_path.exists():
            print_user_message(self.passed_path.read_text())
        else:
            super().test_passed()