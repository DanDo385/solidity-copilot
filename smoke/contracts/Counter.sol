pragma solidity ^0.8.30;

contract Counter {
    uint256 public count;

    event CountChanged(uint256 oldCount, uint256 newCount);

    function increment() public {
        uint256 oldCount = count;
        count += 1;
        emit CountChanged(oldCount, count);
    }

    function reset() public {
        uint256 oldCount = count;
        count = 0;
        emit CountChanged(oldCount, 0);
    }
}
