/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * @exports Tasks
 */

'use strict';

var _ = require('lodash');
var React = require('react');
var Row = require('react-bootstrap/lib/Row');
var Col = require('react-bootstrap/lib/Col');
var ListGroup = require('react-bootstrap/lib/ListGroup');
var ListGroupItem = require('react-bootstrap/lib/ListGroupItem');

var Task = require('./Task.jsx');

/**
 * A list of items that contain form fields for modifying resource limits on specific tasks.
 */
var Tasks = React.createClass({

    render: function () {

        var taskComponents = ['import_reads', 'pathoscope', 'nuvs', 'rebuild', 'add_host'].map(function (taskPrefix) {
            return <Task key={taskPrefix} taskPrefix={taskPrefix} {...this.props} />;
        }, this);

        var title = (
            <ListGroupItem key='title'>
                <Row>
                    <Col md={4}>CPU</Col>
                    <Col md={4}>Memory (GB)</Col>
                    <Col md={4}>Concurrent Jobs</Col>
                </Row>
            </ListGroupItem>
        );

        return (
            <ListGroup>
                {title}
                {taskComponents}
            </ListGroup>
        );
    }

});

module.exports = Tasks;