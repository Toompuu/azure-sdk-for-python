# coding=utf-8
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

# pylint: disable=protected-access

import json
from typing import (
    Any,
    Dict,
    Union,
    List,
    TYPE_CHECKING,
)
from azure.core.tracing.decorator import distributed_trace
from azure.core.polling import LROPoller
from azure.core.polling.base_polling import LROBasePolling
from azure.core.pipeline import Pipeline
from ._helpers import TransportWrapper
from ._api_versions import FormRecognizerApiVersion
from ._models import (
    CustomFormModelInfo,
    AccountProperties,
    CustomFormModel,
)
from ._polling import FormTrainingPolling, CopyPolling
from ._form_recognizer_client import FormRecognizerClient
from ._form_base_client import FormRecognizerClientBase

if TYPE_CHECKING:
    from azure.core.credentials import AzureKeyCredential, TokenCredential
    from azure.core.pipeline import PipelineResponse
    from azure.core.pipeline.transport import HttpResponse
    from azure.core.paging import ItemPaged

    PipelineResponseType = HttpResponse


class FormTrainingClient(FormRecognizerClientBase):
    """FormTrainingClient is the Form Recognizer interface to use for creating
    and managing custom models. It provides methods for training models on the forms
    you provide, as well as methods for viewing and deleting models, accessing
    account properties, copying models to another Form Recognizer resource, and
    composing models from a collection of existing models trained with labels.

    .. note:: FormTrainingClient should be used with API versions <=v2.1.
        To use API versions 2021-09-30-preview and up, instantiate a DocumentModelAdministrationClient.

    :param str endpoint: Supported Cognitive Services endpoints (protocol and hostname,
        for example: https://westus2.api.cognitive.microsoft.com).
    :param credential: Credentials needed for the client to connect to Azure.
        This is an instance of AzureKeyCredential if using an API key or a token
        credential from :mod:`azure.identity`.
    :type credential: :class:`~azure.core.credentials.AzureKeyCredential` or
        :class:`~azure.core.credentials.TokenCredential`
    :keyword api_version:
        The API version of the service to use for requests. It defaults to API version v2.1.
        Setting to an older version may result in reduced feature compatibility. To use the
        latest supported API version and features, instantiate a DocumentModelAdministrationClient instead.
    :paramtype api_version: str or ~azure.ai.formrecognizer.FormRecognizerApiVersion

    .. admonition:: Example:

        .. literalinclude:: ../samples/v3.1/sample_authentication.py
            :start-after: [START create_ft_client_with_key]
            :end-before: [END create_ft_client_with_key]
            :language: python
            :dedent: 8
            :caption: Creating the FormTrainingClient with an endpoint and API key.

        .. literalinclude:: ../samples/v3.1/sample_authentication.py
            :start-after: [START create_ft_client_with_aad]
            :end-before: [END create_ft_client_with_aad]
            :language: python
            :dedent: 8
            :caption: Creating the FormTrainingClient with a token credential.
    """

    def __init__(self, endpoint, credential, **kwargs):
        # type: (str, Union[AzureKeyCredential, TokenCredential], Any) -> None
        api_version = kwargs.pop("api_version", FormRecognizerApiVersion.V2_1)
        super(FormTrainingClient, self).__init__(
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
            client_kind="form",
            **kwargs
        )

    @distributed_trace
    def begin_training(self, training_files_url, use_training_labels, **kwargs):
        # type: (str, bool, Any) -> LROPoller[CustomFormModel]
        """Create and train a custom model. The request must include a `training_files_url` parameter that is an
        externally accessible Azure storage blob container URI (preferably a Shared Access Signature URI). Note that
        a container URI (without SAS) is accepted only when the container is public or has a managed identity
        configured, see more about configuring managed identities to work with Form Recognizer here:
        https://docs.microsoft.com/azure/applied-ai-services/form-recognizer/managed-identities.
        Models are trained using documents that are of the following content type - 'application/pdf',
        'image/jpeg', 'image/png', 'image/tiff', or 'image/bmp'. Other types of content in the container is ignored.

        :param str training_files_url: An Azure Storage blob container's SAS URI. A container URI (without SAS)
            can be used if the container is public or has a managed identity configured. For more information on
            setting up a training data set, see: https://aka.ms/azsdk/formrecognizer/buildtrainingset.
        :param bool use_training_labels: Whether to train with labels or not. Corresponding labeled files must
            exist in the blob container if set to `True`.
        :keyword str prefix: A case-sensitive prefix string to filter documents in the source path for
            training. For example, when using an Azure storage blob URI, use the prefix to restrict sub
            folders for training.
        :keyword bool include_subfolders: A flag to indicate if subfolders within the set of prefix folders
            will also need to be included when searching for content to be preprocessed. Not supported if
            training with labels.
        :keyword str model_name: An optional, user-defined name to associate with your model.
        :keyword str continuation_token: A continuation token to restart a poller from a saved state.
        :return: An instance of an LROPoller. Call `result()` on the poller
            object to return a :class:`~azure.ai.formrecognizer.CustomFormModel`.
        :rtype: ~azure.core.polling.LROPoller[~azure.ai.formrecognizer.CustomFormModel]
        :raises ~azure.core.exceptions.HttpResponseError:
            Note that if the training fails, the exception is raised, but a model with an
            "invalid" status is still created. You can delete this model by calling :func:`~delete_model()`

        .. versionadded:: v2.1
            The *model_name* keyword argument

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_train_model_without_labels.py
                :start-after: [START training]
                :end-before: [END training]
                :language: python
                :dedent: 8
                :caption: Training a model (without labels) with your custom forms.
        """

        def callback_v2_0(raw_response):
            model = self._deserialize(self._generated_models.Model, raw_response)
            return CustomFormModel._from_generated(model, api_version=self._api_version)

        def callback_v2_1(raw_response, _, headers):  # pylint: disable=unused-argument
            model = self._deserialize(self._generated_models.Model, raw_response)
            return CustomFormModel._from_generated(model, api_version=self._api_version)

        cls = kwargs.pop("cls", None)
        model_name = kwargs.pop("model_name", None)
        continuation_token = kwargs.pop("continuation_token", None)
        polling_interval = kwargs.pop(
            "polling_interval", self._client._config.polling_interval
        )

        if model_name and self._api_version == "2.0":
            raise ValueError(
                "'model_name' is only available for API version V2_1 and up"
            )

        if self._api_version == "2.0":
            deserialization_callback = cls if cls else callback_v2_0
            if continuation_token:
                return LROPoller.from_continuation_token(
                    polling_method=LROBasePolling(
                        timeout=polling_interval,
                        lro_algorithms=[FormTrainingPolling()],
                        **kwargs
                    ),
                    continuation_token=continuation_token,
                    client=self._client._client,
                    deserialization_callback=deserialization_callback,
                )

            response = self._client.train_custom_model_async(  # type: ignore
                train_request=self._generated_models.TrainRequest(
                    source=training_files_url,
                    use_label_file=use_training_labels,
                    source_filter=self._generated_models.TrainSourceFilter(
                        prefix=kwargs.pop("prefix", ""),
                        include_sub_folders=kwargs.pop("include_subfolders", False),
                    ),
                ),
                cls=lambda pipeline_response, _, response_headers: pipeline_response,
                **kwargs
            )  # type: PipelineResponseType

            return LROPoller(
                self._client._client,
                response,
                deserialization_callback,
                LROBasePolling(
                    timeout=polling_interval,
                    lro_algorithms=[FormTrainingPolling()],
                    **kwargs
                ),
            )

        deserialization_callback = cls if cls else callback_v2_1
        return self._client.begin_train_custom_model_async(  # type: ignore
            train_request=self._generated_models.TrainRequest(
                source=training_files_url,
                use_label_file=use_training_labels,
                source_filter=self._generated_models.TrainSourceFilter(
                    prefix=kwargs.pop("prefix", ""),
                    include_sub_folders=kwargs.pop("include_subfolders", False),
                ),
                model_name=model_name,
            ),
            cls=deserialization_callback,
            continuation_token=continuation_token,
            polling=LROBasePolling(
                timeout=polling_interval,
                lro_algorithms=[FormTrainingPolling()],
                **kwargs
            ),
            **kwargs
        )

    @distributed_trace
    def delete_model(self, model_id, **kwargs):
        # type: (str, Any) -> None
        """Mark model for deletion. Model artifacts will be permanently
        removed within a predetermined period.

        :param model_id: Model identifier.
        :type model_id: str
        :rtype: None
        :raises ~azure.core.exceptions.HttpResponseError or ~azure.core.exceptions.ResourceNotFoundError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_manage_custom_models.py
                :start-after: [START delete_model]
                :end-before: [END delete_model]
                :language: python
                :dedent: 8
                :caption: Delete a custom model.
        """

        if not model_id:
            raise ValueError("model_id cannot be None or empty.")

        self._client.delete_custom_model(model_id=model_id, **kwargs)

    @distributed_trace
    def list_custom_models(self, **kwargs):
        # type: (Any) -> ItemPaged[CustomFormModelInfo]
        """List information for each model, including model id,
        model status, and when it was created and last modified.

        :return: ItemPaged[:class:`~azure.ai.formrecognizer.CustomFormModelInfo`]
        :rtype: ~azure.core.paging.ItemPaged
        :raises ~azure.core.exceptions.HttpResponseError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_manage_custom_models.py
                :start-after: [START list_custom_models]
                :end-before: [END list_custom_models]
                :language: python
                :dedent: 8
                :caption: List model information for each model on the account.
        """
        return self._client.list_custom_models(  # type: ignore
            cls=kwargs.pop(
                "cls",
                lambda objs: [
                    CustomFormModelInfo._from_generated(
                        x, api_version=self._api_version
                    )
                    for x in objs
                ],
            ),
            **kwargs
        )

    @distributed_trace
    def get_account_properties(self, **kwargs):
        # type: (Any) -> AccountProperties
        """Get information about the models on the form recognizer account.

        :return: Summary of models on account - custom model count,
            custom model limit.
        :rtype: ~azure.ai.formrecognizer.AccountProperties
        :raises ~azure.core.exceptions.HttpResponseError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_manage_custom_models.py
                :start-after: [START get_account_properties]
                :end-before: [END get_account_properties]
                :language: python
                :dedent: 8
                :caption: Get properties for the form recognizer account.
        """
        response = self._client.get_custom_models(**kwargs)
        return AccountProperties._from_generated(response.summary)

    @distributed_trace
    def get_custom_model(self, model_id, **kwargs):
        # type: (str, Any) -> CustomFormModel
        """Get a description of a custom model, including the types of forms
        it can recognize, and the fields it will extract for each form type.

        :param str model_id: Model identifier.
        :return: CustomFormModel
        :rtype: ~azure.ai.formrecognizer.CustomFormModel
        :raises ~azure.core.exceptions.HttpResponseError or ~azure.core.exceptions.ResourceNotFoundError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_manage_custom_models.py
                :start-after: [START get_custom_model]
                :end-before: [END get_custom_model]
                :language: python
                :dedent: 8
                :caption: Get a custom model with a model ID.
        """

        if not model_id:
            raise ValueError("model_id cannot be None or empty.")

        response = self._client.get_custom_model(
            model_id=model_id, include_keys=True, **kwargs
        )
        if (
            hasattr(response, "composed_train_results")
            and response.composed_train_results  # type: ignore
        ):
            return CustomFormModel._from_generated_composed(response)
        return CustomFormModel._from_generated(response, api_version=self._api_version)

    @distributed_trace
    def get_copy_authorization(self, resource_id, resource_region, **kwargs):
        # type: (str, str, Any) -> Dict[str, Union[str, int]]
        """Generate authorization for copying a custom model into the target Form Recognizer resource.
        This should be called by the target resource (where the model will be copied to)
        and the output can be passed as the `target` parameter into :func:`~begin_copy_model()`.

        :param str resource_id: Azure Resource Id of the target Form Recognizer resource
            where the model will be copied to.
        :param str resource_region: Location of the target Form Recognizer resource. A valid Azure
            region name supported by Cognitive Services. For example, 'westus', 'eastus' etc.
            See https://azure.microsoft.com/global-infrastructure/services/?products=cognitive-services
            for the regional availability of Cognitive Services.
        :return: A dictionary with values for the copy authorization -
            "modelId", "accessToken", "resourceId", "resourceRegion", and "expirationDateTimeTicks".
        :rtype: Dict[str, Union[str, int]]
        :raises ~azure.core.exceptions.HttpResponseError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_copy_model.py
                :start-after: [START get_copy_authorization]
                :end-before: [END get_copy_authorization]
                :language: python
                :dedent: 8
                :caption: Authorize the target resource to receive the copied model
        """

        response = self._client.generate_model_copy_authorization(  # type: ignore
            cls=lambda pipeline_response, deserialized, response_headers: pipeline_response,
            **kwargs
        )  # type: PipelineResponse
        target = json.loads(response.http_response.text())
        target["resourceId"] = resource_id
        target["resourceRegion"] = resource_region
        return target

    @distributed_trace
    def begin_copy_model(
        self,
        model_id,  # type: str
        target,  # type: Dict
        **kwargs  # type: Any
    ):
        # type: (...) -> LROPoller[CustomFormModelInfo]
        """Copy a custom model stored in this resource (the source) to the user specified
        target Form Recognizer resource. This should be called with the source Form Recognizer resource
        (with the model that is intended to be copied). The `target` parameter should be supplied from the
        target resource's output from calling the :func:`~get_copy_authorization()` method.

        :param str model_id: Model identifier of the model to copy to target resource.
        :param dict target:
            The copy authorization generated from the target resource's call to
            :func:`~get_copy_authorization()`.
        :keyword str continuation_token: A continuation token to restart a poller from a saved state.
        :return: An instance of an LROPoller. Call `result()` on the poller
            object to return a :class:`~azure.ai.formrecognizer.CustomFormModelInfo`.
        :rtype: ~azure.core.polling.LROPoller[~azure.ai.formrecognizer.CustomFormModelInfo]
        :raises ~azure.core.exceptions.HttpResponseError:

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_copy_model.py
                :start-after: [START begin_copy_model]
                :end-before: [END begin_copy_model]
                :language: python
                :dedent: 8
                :caption: Copy a model from the source resource to the target resource
        """

        if not model_id:
            raise ValueError("model_id cannot be None or empty.")

        polling_interval = kwargs.pop(
            "polling_interval", self._client._config.polling_interval
        )
        continuation_token = kwargs.pop("continuation_token", None)

        def _copy_callback(raw_response, _, headers):  # pylint: disable=unused-argument
            copy_operation = self._deserialize(
                self._generated_models.CopyOperationResult, raw_response
            )
            model_id = (
                copy_operation.copy_result.model_id
                if hasattr(copy_operation, "copy_result")
                else None
            )
            if model_id:
                return CustomFormModelInfo._from_generated(
                    copy_operation, model_id, api_version=self._api_version
                )
            if target:
                return CustomFormModelInfo._from_generated(
                    copy_operation, target["model_id"], api_version=self._api_version
                )
            return CustomFormModelInfo._from_generated(
                copy_operation, None, api_version=self._api_version
            )

        return self._client.begin_copy_custom_model(  # type: ignore
            model_id=model_id,
            copy_request=self._generated_models.CopyRequest(
                target_resource_id=target["resourceId"],
                target_resource_region=target["resourceRegion"],
                copy_authorization=self._generated_models.CopyAuthorizationResult(
                    access_token=target["accessToken"],
                    model_id=target["modelId"],
                    expiration_date_time_ticks=target["expirationDateTimeTicks"],
                ),
            )
            if target
            else None,
            cls=kwargs.pop("cls", _copy_callback),
            polling=LROBasePolling(
                timeout=polling_interval, lro_algorithms=[CopyPolling()], **kwargs
            ),
            continuation_token=continuation_token,
            **kwargs
        )

    @distributed_trace
    def begin_create_composed_model(self, model_ids, **kwargs):
        # type: (List[str], Any) -> LROPoller[CustomFormModel]
        """Creates a composed model from a collection of existing models that were trained with labels.

        A composed model allows multiple models to be called with a single model ID. When a document is
        submitted to be analyzed with a composed model ID, a classification step is first performed to
        route it to the correct custom model.

        :param list[str] model_ids: List of model IDs to use in the composed model.
        :keyword str model_name: An optional, user-defined name to associate with your model.
        :keyword str continuation_token: A continuation token to restart a poller from a saved state.
        :return: An instance of an LROPoller. Call `result()` on the poller
            object to return a :class:`~azure.ai.formrecognizer.CustomFormModel`.
        :rtype: ~azure.core.polling.LROPoller[~azure.ai.formrecognizer.CustomFormModel]
        :raises ~azure.core.exceptions.HttpResponseError:

        .. versionadded:: v2.1
            The *begin_create_composed_model* client method

        .. admonition:: Example:

            .. literalinclude:: ../samples/v3.1/sample_create_composed_model.py
                :start-after: [START begin_create_composed_model]
                :end-before: [END begin_create_composed_model]
                :language: python
                :dedent: 8
                :caption: Create a composed model
        """

        def _compose_callback(
            raw_response, _, headers
        ):  # pylint: disable=unused-argument
            model = self._deserialize(self._generated_models.Model, raw_response)
            return CustomFormModel._from_generated_composed(model)

        model_name = kwargs.pop("model_name", None)
        polling_interval = kwargs.pop(
            "polling_interval", self._client._config.polling_interval
        )
        continuation_token = kwargs.pop("continuation_token", None)
        try:
            return self._client.begin_compose_custom_models_async(  # type: ignore
                {"model_ids": model_ids, "model_name": model_name}, # type: ignore
                cls=kwargs.pop("cls", _compose_callback),
                polling=LROBasePolling(
                    timeout=polling_interval,
                    lro_algorithms=[FormTrainingPolling()],
                    **kwargs
                ),
                continuation_token=continuation_token,
                **kwargs
            )
        except ValueError:
            raise ValueError(
                "Method 'begin_create_composed_model' is only available for API version V2_1 and up"
            )

    def get_form_recognizer_client(self, **kwargs):
        # type: (Any) -> FormRecognizerClient
        """Get an instance of a FormRecognizerClient from FormTrainingClient.

        :rtype: ~azure.ai.formrecognizer.FormRecognizerClient
        :return: A FormRecognizerClient
        """

        _pipeline = Pipeline(
            transport=TransportWrapper(self._client._client._pipeline._transport),
            policies=self._client._client._pipeline._impl_policies,
        )  # type: Pipeline
        client = FormRecognizerClient(
            endpoint=self._endpoint,
            credential=self._credential,
            pipeline=_pipeline,
            api_version=self._api_version,
            **kwargs
        )
        # need to share config, but can't pass as a keyword into client
        client._client._config = self._client._client._config
        return client

    def close(self):
        # type: () -> None
        """Close the :class:`~azure.ai.formrecognizer.FormTrainingClient` session."""
        return self._client.close()

    def __enter__(self):
        # type: () -> FormTrainingClient
        self._client.__enter__()  # pylint:disable=no-member
        return self

    def __exit__(self, *args):
        # type: (*Any) -> None
        self._client.__exit__(*args)  # pylint:disable=no-member
