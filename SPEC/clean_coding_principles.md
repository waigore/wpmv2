# Clean Coding Principles

## Purpose

This document defines the clean coding principles that all code in the wpmv2 (Wealth Portfolio Manager) project must adhere to. These principles are enforced through code review and should be referenced in all module specifications.

## Principles

### 1. Build Abstractions and Implement Delegation + Encapsulation

**Principle:** Always build abstractions and implement delegation and encapsulation whenever possible. High-level components should never need to know implementation details of lower-level components.

**Examples:**
- The portfolio aggregation logic should never need to know whether it's dealing with a simple portfolio or composite portfolio. Instead, both should implement a common interface that the aggregation logic can delegate to.
- Price retrievers (YahooFinanceRetriever, CoinGeckoRetriever) should be abstracted behind a common PriceRetriever interface, so the pricing module doesn't need to know which specific retriever to use.
- Components should encapsulate their internal state and expose only necessary interfaces.
- Use factory patterns, dependency injection, and interface abstractions to decouple components.

**Enforcement:**
- When reviewing code, verify that high-level orchestration code (like portfolio aggregation) does not contain implementation-specific logic for different portfolio types.
- Check that price retrievers implement a common interface/contract rather than requiring custom handling in the pricing module.
- Ensure that internal implementation details are not exposed beyond module boundaries.

### 2. Avoid Nested Conditionals - Use Conditional Guards

**Principle:** Nested conditionals are a code smell and should be avoided. Prefer conditional guards (early returns/continues) to flatten control logic. If control logic is still too complicated (e.g., 3 or more nested layers), abstract it away into a class or function.

**Rule:** Never have more than 2 levels of nested if statements.

**Examples:**

**Bad:**
```python
if condition_a:
    if condition_b:
        if condition_c:
            # do work
        else:
            pass
    else:
        pass
else:
    pass
```

**Better (with guards):**
```python
if not condition_a:
    return  # or continue, or handle early case

if not condition_b:
    return

if not condition_c:
    return

# do work
```

**When to Abstract:**
- If after applying guard clauses, you still have 3+ levels of nesting, extract the logic into a separate function or class.
- Complex conditional logic that represents a distinct decision point should be encapsulated in a method with a descriptive name.

**Enforcement:**
- Code reviews must flag any code with more than 2 levels of nested conditionals.
- Prefer guard clauses (`if not condition: return/continue`) over nested if-else blocks.
- Extract complex conditional logic into well-named helper methods or classes.

### 3. Avoid Inline Imports

**Principle:** Avoid inline imports (imports inside functions or methods) as they build hidden dependencies and contribute to undesired coupling. All imports should be at the module level.

**Rationale:**
- Inline imports make dependencies less visible and harder to track.
- They can create circular import issues.
- They make it difficult to understand module dependencies at a glance.
- They can lead to performance issues if imports happen in hot paths.

**Examples:**

**Bad:**
```python
def calculate_portfolio_metrics(portfolio):
    from wpm.pricing import PriceRetriever
    from wpm.cost_basis import calculate_fifo_cost_basis
    retriever = PriceRetriever()
    positions = calculate_fifo_cost_basis(portfolio.trades)
    # ...
```

**Better:**
```python
from wpm.pricing import PriceRetriever
from wpm.cost_basis import calculate_fifo_cost_basis

def calculate_portfolio_metrics(portfolio):
    retriever = PriceRetriever()
    positions = calculate_fifo_cost_basis(portfolio.trades)
    # ...
```

**Exceptions:**
- Only acceptable when importing inside a function is necessary to break a circular import, and this should be documented with a comment explaining why.

**Enforcement:**
- All imports must be at the top of the file (after module docstring and before any other code).
- Code reviews must flag any inline imports and require justification if they cannot be moved to module level.

### 4. Avoid hasattr Unless Absolutely Necessary

**Principle:** Avoid using `hasattr()` unless absolutely necessary. `hasattr` degrades code quality and makes the program more brittle during execution.

**Rationale:**
- `hasattr` relies on dynamic attribute access, which bypasses static type checking and makes code harder to reason about.
- It creates implicit contracts that are not enforced by the type system or class definitions.
- Code using `hasattr` is more prone to runtime errors that could be caught earlier with proper type checking or explicit interfaces.
- It encourages a "duck typing gone wrong" approach where objects are expected to have certain attributes without clear guarantees.
- Makes refactoring more dangerous as attribute existence checks can silently fail or pass incorrectly.

**Examples:**

**Bad:**
```python
def get_price(ticker, asset_type):
    if hasattr(retriever, 'get_stock_price'):
        return retriever.get_stock_price(ticker)
    if hasattr(retriever, 'get_crypto_price'):
        return retriever.get_crypto_price(ticker)
    return retriever.get_price(ticker)
```

**Better (using interfaces/abstract base classes):**
```python
from abc import ABC, abstractmethod

class PriceRetriever(ABC):
    @abstractmethod
    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get price for an asset, regardless of type."""
        pass

class YahooFinanceRetriever(PriceRetriever):
    def get_price(self, ticker: str, asset_type: str) -> float:
        # Implementation for stocks/ETFs
        pass

class CoinGeckoRetriever(PriceRetriever):
    def get_price(self, ticker: str, asset_type: str) -> float:
        # Implementation for crypto
        pass

def get_price(retriever: PriceRetriever, ticker: str, asset_type: str) -> float:
    return retriever.get_price(ticker, asset_type)
```

**Better (using explicit type checking):**
```python
from typing import Protocol

class PriceRetriever(Protocol):
    def get_price(self, ticker: str, asset_type: str) -> float: ...

def get_price(retriever: PriceRetriever, ticker: str, asset_type: str) -> float:
    return retriever.get_price(ticker, asset_type)
```

**When hasattr is Acceptable:**
- Only when dealing with truly dynamic objects where attribute existence cannot be determined statically (e.g., parsing external data structures, working with third-party libraries that don't provide type hints).
- When the alternative would require significant architectural changes that are not feasible in the short term (should be documented and marked for refactoring).

**Enforcement:**
- Code reviews must flag all uses of `hasattr` and require justification.
- Prefer abstract base classes, protocols, or explicit type checking to define expected interfaces.
- Use optional methods with default implementations in base classes rather than checking for attribute existence.
- Document any legitimate uses of `hasattr` with comments explaining why it's necessary.

### 5. Segregate Cache Files Between Production and Testing Environments

**Principle:** Cache files must be segregated between production and testing environments. Tests should never write to or read from production cache files.

**Rationale:**
- Tests should be isolated from production data to prevent contamination and ensure reproducible test results.
- Production cache files should not be modified by test runs, which could affect real-world usage.
- Test isolation ensures that tests can run safely in parallel or in CI/CD environments without affecting user data.
- Prevents test failures due to stale or corrupted production cache data.
- Allows tests to have predictable, controlled cache states for testing different scenarios.

**Enforcement:**
- Global test configuration must automatically redirect all cache operations to a test-specific directory.
- All cache classes (PriceCache, CurrencyCache, HistoricalPriceCache, AssetMetadataCache) must use test cache paths when running in test environment.
- Tests should not need to explicitly configure cache paths - this should be handled automatically by test infrastructure.
- Production cache directory (`~/.wpm/`) must never be accessed during test execution.

**Implementation:**
- Use pytest session-scoped autouse fixtures to override `Config` class variables for all cache file paths.
- Test cache directory should be a temporary directory that is cleaned up after test execution.
- Cache classes should respect the overridden `Config` values, ensuring they use test cache paths when `cache_file` parameter is not explicitly provided.

**Examples:**

**Bad (test using production cache):**
```python
def test_get_price():
    service = PriceService()  # Uses Config.CACHE_FILE (~/.wpm/price_cache.parquet)
    price = service.get_price("GOOG", "Stock")  # Writes to production cache!
```

**Better (automatic test cache isolation):**
```python
# conftest.py provides automatic cache isolation
def test_get_price():
    service = PriceService()  # Automatically uses test cache directory
    price = service.get_price("GOOG", "Stock")  # Writes to test cache only
```

**Better (explicit test cache for specific test needs):**
```python
def test_specific_cache_scenario():
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_file = Path(temp_dir) / "custom_cache.parquet"
        service = PriceService(cache_file=cache_file)  # Explicit override still works
        # Test with specific cache state
```

## Integration with Specifications

All module specifications should reference this document and explicitly state how the module adheres to these principles:

- **Abstraction/Delegation:** Describe the interfaces and abstractions the module provides.
- **Control Flow:** Note any complex conditional logic and how it's been flattened or abstracted.
- **Dependencies:** List all module-level imports and explain the module's dependencies.
- **Type Safety:** Document any use of `hasattr` and justify why it's necessary, or describe the explicit interfaces/protocols used instead.

## Code Review Checklist

When reviewing code, verify:

- [ ] No more than 2 levels of nested conditionals
- [ ] Guard clauses are used to flatten control flow
- [ ] Complex logic is abstracted into functions/classes
- [ ] All imports are at module level (no inline imports)
- [ ] High-level components delegate to abstractions rather than implementing details
- [ ] Dependencies are explicit and visible
- [ ] `hasattr` is avoided unless absolutely necessary (with documented justification)
- [ ] Interfaces are defined using abstract base classes, protocols, or explicit type checking
- [ ] Tests use test-specific cache directories and never access production cache files

## References

- See `SPEC/spec.md` for module-level requirements and architecture details
- These principles apply to all code in the wpmv2 (Wealth Portfolio Manager) project

