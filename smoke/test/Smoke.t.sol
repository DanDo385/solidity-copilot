// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Counter} from "../contracts/Counter.sol";
import {PiggyBank} from "../contracts/PiggyBank.sol";
import {SimpleToken} from "../contracts/SimpleToken.sol";

interface Vm {
    function deal(address account, uint256 newBalance) external;
    function expectEmit(bool checkTopic1, bool checkTopic2, bool checkTopic3, bool checkData)
        external;
    function expectRevert() external;
    function expectRevert(bytes4 revertData) external;
    function expectRevert(bytes calldata revertData) external;
    function prank(address msgSender) external;
}

abstract contract TestBase {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    function assertEq(uint256 actual, uint256 expected, string memory message) internal pure {
        require(actual == expected, message);
    }

    function assertEq(address actual, address expected, string memory message) internal pure {
        require(actual == expected, message);
    }

    function assertEq(string memory actual, string memory expected, string memory message)
        internal
        pure
    {
        require(keccak256(bytes(actual)) == keccak256(bytes(expected)), message);
    }

    function assertTrue(bool condition, string memory message) internal pure {
        require(condition, message);
    }
}

contract CounterSmokeTest is TestBase {
    event CountChanged(uint256 oldCount, uint256 newCount);

    Counter private counter;

    function setUp() public {
        counter = new Counter();
    }

    function testInitialCountIsZero() public view {
        assertEq(counter.count(), 0, "initial count");
    }

    function testAnyoneCanIncrementAndEmitChange() public {
        address caller = address(0xBEEF);
        vm.expectEmit(false, false, false, true);
        emit CountChanged(0, 1);
        vm.prank(caller);
        counter.increment();
        assertEq(counter.count(), 1, "incremented count");
    }

    function testAnyoneCanResetAndEmitChange() public {
        counter.increment();
        vm.expectEmit(false, false, false, true);
        emit CountChanged(1, 0);
        vm.prank(address(0xBEEF));
        counter.reset();
        assertEq(counter.count(), 0, "reset count");
    }
}

contract PiggyBankSmokeTest is TestBase {
    event Deposited(address indexed sender, uint256 amount);
    event Withdrawn(address indexed owner, uint256 amount);

    PiggyBank private piggyBank;

    receive() external payable {}

    function setUp() public {
        piggyBank = new PiggyBank();
    }

    function testDeployerIsOwner() public view {
        assertEq(piggyBank.owner(), address(this), "owner");
    }

    function testReceiveAcceptsEtherAndEmitsDeposit() public {
        address depositor = address(0xBEEF);
        vm.deal(depositor, 1 ether);
        vm.expectEmit(true, false, false, true);
        emit Deposited(depositor, 1 ether);
        vm.prank(depositor);
        (bool success,) = address(piggyBank).call{value: 1 ether}("");
        assertTrue(success, "deposit call");
        assertEq(address(piggyBank).balance, 1 ether, "deposit balance");
    }

    function testNonOwnerCannotWithdraw() public {
        address other = address(0xBEEF);
        vm.expectRevert(abi.encodeWithSelector(PiggyBank.Unauthorized.selector, other));
        vm.prank(other);
        piggyBank.withdrawAll();
    }

    function testOwnerWithdrawsFullBalanceAndEmitsEvent() public {
        vm.deal(address(piggyBank), 1 ether);
        vm.expectEmit(true, false, false, true);
        emit Withdrawn(address(this), 1 ether);
        piggyBank.withdrawAll();
        assertEq(address(piggyBank).balance, 0, "post-withdraw balance");
    }

    function testWithdrawalRevertsWhenOwnerRejectsEther() public {
        RejectingOwner rejectingOwner = new RejectingOwner();
        vm.deal(address(rejectingOwner.bank()), 1 ether);
        vm.expectRevert();
        rejectingOwner.withdraw();
        assertEq(address(rejectingOwner.bank()).balance, 1 ether, "reverted withdrawal balance");
    }
}

contract RejectingOwner {
    PiggyBank public immutable bank;

    constructor() {
        bank = new PiggyBank();
    }

    receive() external payable {
        revert("reject ether");
    }

    function withdraw() external {
        bank.withdrawAll();
    }
}

contract SimpleTokenSmokeTest is TestBase {
    SimpleToken private token;
    address private recipient = address(0xBEEF);

    function setUp() public {
        token = new SimpleToken(100);
    }

    function testMetadataAndInitialSupply() public view {
        assertEq(token.name(), "Smoke Token", "name");
        assertEq(token.symbol(), "SMOKE", "symbol");
        assertEq(token.decimals(), 18, "decimals");
        assertEq(token.totalSupply(), 100, "total supply");
        assertEq(token.balanceOf(address(this)), 100, "deployer balance");
    }

    function testTransferUpdatesBalancesAndEmitsEvent() public {
        vm.expectEmit(true, true, false, true);
        emit SimpleToken.Transfer(address(this), recipient, 25);
        assertTrue(token.transfer(recipient, 25), "transfer return");
        assertEq(token.balanceOf(address(this)), 75, "sender balance");
        assertEq(token.balanceOf(recipient), 25, "recipient balance");
    }

    function testTransferRejectsZeroAddress() public {
        vm.expectRevert(SimpleToken.ZeroAddress.selector);
        token.transfer(address(0), 1);
    }

    function testTransferRejectsInsufficientBalance() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                SimpleToken.InsufficientBalance.selector, uint256(100), uint256(101)
            )
        );
        token.transfer(recipient, 101);
    }
}
