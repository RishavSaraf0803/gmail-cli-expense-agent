"""
Prompt Manager for loading, versioning, and managing LLM prompts.
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from string import Template

from fincli.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTemplate:
    """Represents a versioned prompt template."""
    name: str
    version: str
    system_prompt: str
    user_template: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any]

    def render_user_prompt(self, **kwargs) -> str:
        """
        Render user prompt with variables.

        Args:
            **kwargs: Variables to substitute in template

        Returns:
            Rendered prompt string
        """
        template = Template(self.user_template)
        return template.safe_substitute(**kwargs)

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self.parameters.get(key, default)


class PromptManager:
    """
    Manage versioned prompts loaded from YAML files.

    Features:
    - Load prompts from YAML files
    - Version management
    - Template rendering
    - A/B testing support
    - Prompt performance tracking
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt manager.

        Args:
            prompts_dir: Directory containing prompt YAML files.
                        Defaults to fincli/prompts/
        """
        if prompts_dir is None:
            # Default to fincli/prompts/ directory
            prompts_dir = Path(__file__).parent

        self.prompts_dir = Path(prompts_dir)
        self.prompts_cache: Dict[str, PromptTemplate] = {}

        logger.info("prompt_manager_initialized", dir=str(self.prompts_dir))

    def _load_prompt_file(self, file_path: Path) -> PromptTemplate:
        """
        Load a prompt from YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            PromptTemplate object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            # Validate required fields
            required_fields = ['name', 'version', 'system_prompt', 'user_template']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            template = PromptTemplate(
                name=data['name'],
                version=data['version'],
                system_prompt=data['system_prompt'],
                user_template=data['user_template'],
                parameters=data.get('parameters', {}),
                metadata=data.get('metadata', {})
            )

            logger.info(
                "prompt_loaded",
                name=template.name,
                version=template.version,
                file=file_path.name
            )

            return template

        except yaml.YAMLError as e:
            logger.error("yaml_parse_error", file=str(file_path), error=str(e))
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            logger.error("prompt_load_error", file=str(file_path), error=str(e))
            raise

    def load_prompt(
        self,
        category: str,
        name: str,
        version: Optional[str] = None,
        use_cache: bool = True
    ) -> PromptTemplate:
        """
        Load a prompt by category and name.

        Args:
            category: Prompt category (extraction, chat, analysis)
            name: Prompt name
            version: Specific version to load (e.g., 'v1', 'v2').
                    If None, loads latest version.
            use_cache: Whether to use cached prompts

        Returns:
            PromptTemplate object

        Example:
            >>> manager = PromptManager()
            >>> prompt = manager.load_prompt('extraction', 'transaction', 'v1')
            >>> rendered = prompt.render_user_prompt(email_content="...")
        """
        cache_key = f"{category}/{name}_{version or 'latest'}"

        # Check cache
        if use_cache and cache_key in self.prompts_cache:
            logger.debug("prompt_cache_hit", key=cache_key)
            return self.prompts_cache[cache_key]

        # Construct file path
        if version:
            filename = f"{name}_{version}.yaml"
        else:
            # Find latest version
            filename = self._find_latest_version(category, name)

        file_path = self.prompts_dir / category / filename

        # Load prompt
        template = self._load_prompt_file(file_path)

        # Cache it
        if use_cache:
            self.prompts_cache[cache_key] = template

        return template

    def _find_latest_version(self, category: str, name: str) -> str:
        """
        Find the latest version of a prompt.

        Args:
            category: Prompt category
            name: Prompt name

        Returns:
            Filename of latest version

        Raises:
            FileNotFoundError: If no versions found
        """
        category_dir = self.prompts_dir / category

        if not category_dir.exists():
            raise FileNotFoundError(f"Category directory not found: {category}")

        # Find all versions of this prompt
        pattern = f"{name}_v*.yaml"
        versions = list(category_dir.glob(pattern))

        # Also check for files without version suffix
        no_version = category_dir / f"{name}.yaml"
        if no_version.exists():
            versions.append(no_version)

        if not versions:
            raise FileNotFoundError(
                f"No prompt files found for {category}/{name}"
            )

        # Sort by version number (assuming v1, v2, v3 format)
        # If no version suffix, it's considered latest
        def version_key(path: Path) -> int:
            stem = path.stem
            if '_v' in stem:
                try:
                    return int(stem.split('_v')[-1])
                except ValueError:
                    return 0
            return 999  # Files without version are latest

        latest = max(versions, key=version_key)
        return latest.name

    def list_prompts(self, category: Optional[str] = None) -> Dict[str, list]:
        """
        List available prompts.

        Args:
            category: Optional category filter

        Returns:
            Dict mapping categories to list of prompt names
        """
        result = {}

        if category:
            categories = [category]
        else:
            # List all categories
            categories = [
                d.name for d in self.prompts_dir.iterdir()
                if d.is_dir() and not d.name.startswith('_')
            ]

        for cat in categories:
            cat_dir = self.prompts_dir / cat
            if not cat_dir.exists():
                continue

            prompts = []
            for yaml_file in cat_dir.glob("*.yaml"):
                # Extract name (remove version suffix)
                name = yaml_file.stem
                if '_v' in name:
                    name = name.split('_v')[0]

                if name not in prompts:
                    prompts.append(name)

            result[cat] = sorted(prompts)

        return result

    def get_prompt_metadata(
        self,
        category: str,
        name: str,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for a prompt without loading the full template.

        Args:
            category: Prompt category
            name: Prompt name
            version: Optional version

        Returns:
            Metadata dictionary
        """
        template = self.load_prompt(category, name, version)
        return template.metadata

    def clear_cache(self):
        """Clear the prompt cache."""
        self.prompts_cache = {}
        logger.info("prompt_cache_cleared")

    def reload_prompt(self, category: str, name: str, version: Optional[str] = None):
        """
        Reload a prompt from disk, bypassing cache.

        Args:
            category: Prompt category
            name: Prompt name
            version: Optional version
        """
        cache_key = f"{category}/{name}_{version or 'latest'}"
        if cache_key in self.prompts_cache:
            del self.prompts_cache[cache_key]

        return self.load_prompt(category, name, version, use_cache=False)


# Global singleton instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """
    Get prompt manager (singleton pattern).

    Returns:
        Configured PromptManager instance
    """
    global _prompt_manager

    if _prompt_manager is None:
        _prompt_manager = PromptManager()
        logger.info("prompt_manager_singleton_created")

    return _prompt_manager


def reset_prompt_manager():
    """Reset the global prompt manager instance (for testing)."""
    global _prompt_manager
    _prompt_manager = None
    logger.info("prompt_manager_reset")
