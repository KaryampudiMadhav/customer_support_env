# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Customersupportenv environment server components."""

try:
    from .customerSupportEnv_environment import CustomerSupportEnvironment
except ImportError:
    from customerSupportEnv_environment import CustomerSupportEnvironment

__all__ = ["CustomerSupportEnvironment"]
