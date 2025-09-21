# WHEN Language Examples

This directory contains example programs demonstrating various features of the WHEN language.

## Running Examples

```bash
# Basic usage
when examples/clock.when

# Or with Python directly
python when.py examples/clock.when
```

## Example Programs

### 🕐 **clock.when** - Time Keeping
A simple clock that increments seconds, minutes, and hours.
- **Features**: Basic arithmetic, time logic, fo blocks
- **Concepts**: State persistence, automatic incrementing

### 🚦 **traffic_light.when** - State Machine
Traffic light simulation with red/yellow/green states.
- **Features**: State management, timed transitions
- **Concepts**: State machines, timing control

### 🍽️ **restaurant_sim.when** - Complex System
Restaurant management with orders, kitchen, and service.
- **Features**: Multiple concurrent blocks, performance metrics
- **Concepts**: Complex state management, cooperative scheduling

### 🎮 **tic_tac_toe.when** - Interactive Game
Full tic-tac-toe game with player vs AI.
- **Features**: User input, game logic, AI strategy
- **Concepts**: Interactive programs, complex conditionals

### 🔢 **number_guess.when** - Simple Game
Number guessing game with feedback.
- **Features**: User interaction, loops, conditionals
- **Concepts**: Basic game mechanics, input validation

### 🥤 **vending_machine.when** - Interactive Simulation
Vending machine with coin input and product selection.
- **Features**: State management, user commands
- **Concepts**: Command processing, state transitions

### 🐍 **python_modules_demo.when** - Python Integration
Demonstrates importing and using Python modules.
- **Features**: import statements, module functions
- **Concepts**: Python interoperability, math operations

### ⚡ **simple_test.when** - Basic Demo
Simple demonstration of core WHEN features.
- **Features**: Basic blocks, lifecycle management
- **Concepts**: Block types (os, de, fo), start/stop

## Learning Path

1. **Start with**: `simple_test.when` - Basic concepts
2. **Then try**: `clock.when` - State and arithmetic
3. **Next**: `traffic_light.when` - State machines
4. **Interactive**: `number_guess.when` - User input
5. **Advanced**: `restaurant_sim.when` - Complex systems
6. **Games**: `tic_tac_toe.when` - Full interactivity
7. **Integration**: `python_modules_demo.when` - Python modules

## Key Concepts Demonstrated

### Block Types
- **os (One Shot)**: Run once when called
- **de (Declarative)**: Run exactly N times
- **fo (Forever)**: Run until stopped

### Lifecycle Management
- **`.start()`**: Begin execution
- **`.stop()`**: End execution
- **Block status**: Automatically managed

### Conditional Execution
- **`when condition:`**: Reactive programming
- **State-driven logic**: Based on variable values
- **Event handling**: Responding to changes

### Python Integration
- **`import module`**: Standard imports
- **`from module import item`**: Selective imports
- **Module methods**: `math.sin()`, `random.randint()`

## Creating Your Own Examples

When creating new examples:

1. **Start simple** - Focus on one concept
2. **Add comments** - Explain the WHEN-specific parts
3. **Show lifecycle** - Demonstrate start/stop
4. **Use realistic scenarios** - Clock, game, simulation
5. **Test thoroughly** - Make sure it always terminates

### Example Template

```when
# Example: Description of what this demonstrates
# Features: List of WHEN features used

# Variables
state = "initial"
counter = 0

# Helper function (if needed)
def helper_function(x):
    return x * 2

# One-shot setup
os initialize():
    print("Example: Your Example Name")
    print("Demonstrating: Key concepts")

# Timed block (if needed)
de ticker(5):
    counter = counter + 1
    print("Tick", counter)

# Forever block (if needed)
fo monitor():
    when counter > 3:
        print("Halfway point!")

# Main orchestrator
main:
    # Setup phase
    when state == "initial":
        initialize()
        ticker.start()
        monitor.start()
        state = "running"

    # Completion phase
    when counter >= 5:
        print("Example complete!")
        ticker.stop()
        monitor.stop()
        exit()
```

Happy coding with WHEN! 🎉